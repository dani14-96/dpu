from django.shortcuts import render
from django.http import HttpResponse
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.models import Range1d
from bokeh.io import gridplot, vplot
import numpy as np
import itertools
import os
import time
import math
import pickle
import requests
from bs4 import BeautifulSoup

# Create your views here.
def home(request):
	sidebar_links, subdir_log = file_scan('expt')

	context = {
		"sidebar_links": sidebar_links,
	}

	return render(request, "home.html", context)


# Create your views here.
def simple_chart(request):
	sidebar_links, subdir_log = file_scan('expt')

	context = {
		"sidebar_links": sidebar_links,
	}

	return render(request, "simple_chart.html", context)


def vial_num(request, experiment, vial):
	sidebar_links, subdir_log = file_scan('expt')
	vial_count = range(0, 16)
	expt_dir, expt_subdir = file_scan(experiment)
	rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
	evolver_dir = os.path.join(rootdir, 'experiment')
	OD_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "OD", "vial{0}_OD.txt".format(vial))
	gr_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "growthrate", "vial{0}_gr.txt".format(vial))
	temp_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "temp", "vial{0}_temp.txt".format(vial))

	"""
	OD PLOT
	"""

	with open(OD_dir) as f_in:
		data = np.genfromtxt(itertools.islice(f_in, 0, None, 5), delimiter=',')
	if len(data) < 1000:
		data = np.genfromtxt(OD_dir, delimiter=',')


	last_OD_update = time.ctime(os.path.getmtime(OD_dir))

	p = figure(plot_width=700, plot_height=400)
	p.y_range = Range1d(-.05, 2)
	p.xaxis.axis_label = 'Hours'
	p.yaxis.axis_label = 'Optical Density'
	p.line(data[:,0], data[:,1], line_width=1)
	OD_script, OD_div = components(p)
	od_x_range = p.x_range  # Save plot size for later

	"""
	GROWTH RATE PLOT
	"""

	gr_data = np.genfromtxt(gr_dir, delimiter=',', skip_header=2)

	last_grate_update = time.ctime(os.path.getmtime(gr_dir))

	# Quick patch when there's not enough growth rate values
	if gr_data.ndim < 2 or len(gr_data) <= 2:
		gr_data = np.asarray([[0, 0]])  # Avoids exception in p.line(gr.data ...)
		last_grate_update = "Not enough OD data yet!"  # Change time for a warning
	else:
		# Chop out first gr value, biased by the diff between the initial OD and the lower_thresh
		gr_data = gr_data[1:]

	p = figure(plot_width=700, plot_height=400)
	p.y_range = Range1d(0, 1)  # Customize here y-axis range
	p.x_range = od_x_range  # Set same size as the OD plot
	p.xaxis.axis_label = 'Hours'
	p.yaxis.axis_label = 'Growth rate (1/h)'
	p.line(gr_data[:, 0], gr_data[:, 1], legend="growth rate")  # Growth rate
	# p.line(gr_data[:, 0], math.log(2) / gr_data[:, 1], legend="growth rate")  # Generation time

	# Sliding window for average growth rate calculation
	slide_mean = []
	wsize = 10  # Customize window size to calculate the mean
	for i in range(0, len(gr_data[:, 1])):
		if i - wsize < 0:
			j = 0  # Allows plotting first incomplete windows
		else:
			j = i - wsize

		slide_mean.append(np.nanmean(gr_data[j:i+1, 1]))  # Growth rate
		# slide_mean.append(np.nanmean(math.log(2) / gr_data[j:i+1, 1]))  # Generation time

	p.line(gr_data[:, 0], slide_mean, legend="{0} values mean".format(wsize), line_width=1, line_color="red")

	p.legend.orientation = "top_right"

	grate_script, grate_div = components(p)

	"""
	TEMPERATURE PLOT
	"""

	with open(temp_dir) as f_in:
		data = np.genfromtxt(itertools.islice(f_in, 0, None, 10), delimiter=',')
	if len(data) < 1000:
		data = np.genfromtxt(temp_dir, delimiter=',')

	last_temp_update = time.ctime(os.path.getmtime(temp_dir))

	p = figure(plot_width=700, plot_height=400)
	p.y_range = Range1d(25, 45)
	p.x_range = od_x_range  # Set same size as the OD plot
	p.xaxis.axis_label = 'Hours'
	p.yaxis.axis_label = 'Temp (C)'
	p.line(data[:,0], data[:,1], line_width=1)
	temp_script, temp_div = components(p)

	context = {
		"sidebar_links": sidebar_links,
		"experiment": experiment,
		"vial_count": vial_count,
		"vial": vial,
		"OD_script": OD_script,
		"OD_div": OD_div,
		"grate_script": grate_script,
		"grate_div": grate_div,
		"temp_script": temp_script,
		"temp_div": temp_div,
		"last_OD_update": last_OD_update,
		"last_grate_update": last_grate_update,
		"last_temp_update": last_temp_update,
	}

	return render(request, "vial.html", context)


def expt_name(request, experiment):
	sidebar_links, subdir_log = file_scan('expt')
	vial_count = range(0, 16)

	context = {
		"sidebar_links": sidebar_links,
		"experiment": experiment,
		"vial_count": vial_count,
	}

	return render(request, "experiment.html", context)


def dilutions(request, experiment):
	sidebar_links, subdir_log = file_scan('expt')
	vial_count = range(0, 16)
	expt_dir, expt_subdir = file_scan(experiment)
	rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
	evolver_dir = os.path.join(rootdir, 'experiment')
	pump_cal = os.path.join(evolver_dir, expt_subdir[0], "pump_cal.txt")
	bottle_file = os.path.join(evolver_dir, expt_subdir[0], "bottles.txt")
	expt_pickle = os.path.join(evolver_dir, expt_subdir[0], expt_dir[0], expt_dir[0] + ".pickle")

	if not os.path.isfile(bottle_file):
		open(bottle_file, 'w')

	# Update bottle stuff
	if request.POST.get('save-bottle'):
		# Get time and data from request
		timestamp = time.strftime("%d/%m/%Y %H:%M")
		volume = request.POST.getlist("volume")
		vials = request.POST.getlist("vials")

		# Compile info of new bottle file
		header = "# bottle\tvials\tvolume (L)\n"
		for i in range(len(volume)):
			header += f"bottle{i}\t{vials[i]}\t{volume[i]}\t{timestamp}\n"

		# Backup previous configuration file
		backup_tstamp = time.strftime("%Y%m%d_%H%M", time.localtime(os.path.getmtime(bottle_file)))
		os.rename(bottle_file, os.path.join(evolver_dir, expt_subdir[0], "bottles_"+backup_tstamp+".txt"))

		# Save new file
		F = open(bottle_file, "w")
		F.write(header)
		F.close()

	elif request.POST.get('change-bottle'):
		# Get time and data from request
		timestamp = time.strftime("%d/%m/%Y %H:%M")
		change = request.POST.getlist("change")
		change = [int(x) for x in change]
		volume = request.POST.getlist("volume")

		# Read bottle file and update data (without backup)
		old_data = open(bottle_file).readlines()
		new_data = old_data[0]
		for c, data in enumerate(old_data[1:]):
			# variable data has the shape "bottleID	vials	volume0	timestamp0 ... volumeN	timestampN"
			if c in change:
				new_vol = volume[change.index(c)]
				new_data += data.strip('\n') + "\t" + new_vol + "\t" + timestamp + "\n"
			else:
				new_data += data

		F = open(bottle_file, "w")
		F.write(new_data)
		F.close()

	cal = np.genfromtxt(pump_cal, delimiter="\t")
	diluted = []
	efficiency = []
	last = []

	# Calculate total media consumption per vial
	for vial in vial_count:
		pump_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "pump_log", "vial{0}_pump_log.txt".format(vial))
		ODset_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "ODset", "vial{0}_ODset.txt".format(vial))
		data = np.genfromtxt(pump_dir, delimiter=',', skip_header=2)

		dil_triggered = len(data)

		if dil_triggered != 0:
			volume = str(round(sum(data[:, 1]) * cal[0, vial] / 1000, 2))

			dil_intervals = len(np.genfromtxt(ODset_dir, delimiter=",", skip_header=2)) / 2
			if dil_intervals != 0:
				extra_dils = dil_triggered - dil_intervals
				vial_eff = (dil_intervals - extra_dils) / dil_intervals * 100
			else:
				# Experiment is chemostat or vial is not used
				vial_eff = 0

		else:
			volume = 0
			vial_eff = 0

		diluted.append(volume)
		efficiency.append(str(round(vial_eff, 1)))
		last.append(time.ctime(os.path.getmtime(pump_dir)))

	last_dilution = max(last)

	if efficiency == ['0']*16:
		# All vials were chemostats or not used
		efficiency = None

	# Calculate consumption of last bottle
	bottles = []
	bottle_info = []  # Stores info displayed in "See bottle setup"
	bottle_data = open(bottle_file).readlines()[1:]

	# Get experiment start time
	with open(expt_pickle, 'rb') as f:
		expt_start = pickle.load(f)[0]

	if not bottle_data:
		bottle_info = None
	else:
		# bottleID	vials	volume0	timestamp0 ... volumeN	timestampN
		for c, bot in enumerate(bottle_data):
			# Extract data and store as lists for Django
			bot = bot.strip("\n").split("\t")
			bottle_info.append(bot[:2] + bot[-2:])   # ID	vials	volumeN	timestampN
			# Sum media consumption of vials connected to each bottle
			media = 0
			for v in bot[1].split(","):
				if v:
					# get bottle timestamp
					tstamp = time.mktime(time.strptime(bot[-1], "%d/%m/%Y %H:%M"))  # Timestamp in seconds since epoch
					tstamp -= expt_start  # Timestamp in seconds since start of experiment
					# get data slice from timestamp to present
					pump_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "pump_log", f"vial{v}_pump_log.txt")
					data = np.genfromtxt(pump_dir, delimiter=',', skip_header=2)
					try:
						bottle_consumption = sum(sum(data[np.where(data[:, 0] > tstamp), 1])) * cal[0, int(v)] / 1000
					except IndexError:
						bottle_consumption = -1  # Error when slicing the data
				else:
					bottle_consumption = -2  # Bottle has no vials assigned
					# media += float(diluted[int(v)])  # Old way: sums all experiment consumption

			bottles.append("%.2f / %sL" % (bottle_consumption, bot[-2]))

	context = {
	"sidebar_links": sidebar_links,
	"experiment": experiment,
	"vial_count": vial_count,
	"diluted": diluted,
	"efficiency": efficiency,
	"bottle_info": bottle_info,
	"bottles": bottles,
	"last_dilution": last_dilution
	}

	return render(request, "dilutions.html", context)


def bker(request, experiment):
	sidebar_links, subdir_log = file_scan('expt')
	vial_count = range(0, 16)
	expt_dir, expt_subdir = file_scan(experiment)
	rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
	evolver_dir = os.path.join(rootdir, 'experiment')
	pump_cal = os.path.join(evolver_dir, expt_subdir[0], "pump_cal.txt")
	bottle_file = os.path.join(evolver_dir, expt_subdir[0], "bottles.txt")
	balance_dir = os.path.join(evolver_dir, expt_subdir[0], "balances")
	expt_pickle = os.path.join(evolver_dir, expt_subdir[0], expt_dir[0], expt_dir[0] + ".pickle")

	if not os.path.isdir(balance_dir):
		os.mkdir(balance_dir)

	url = "http://bker.io/profil/probeDetail/"
	probes = [5436, 5556, 5557]
	names = ["Balance1", "Balance3", "Balance4"]

	payload = {
		"Email": "dgruano",
		"Password": "SyntheCell",
		"RememberMe": "false"
	}

	with requests.Session() as s:
		login_page = s.get("http://bker.io/compte/login").text
		Token = BeautifulSoup(login_page).find("input", {"name": "__RequestVerificationToken"})['value']

		payload["__RequestVerificationToken"] = Token

		login = s.post("http://bker.io/compte/login?ReturnUrl=%2Fprofil", data=payload)

		balances = []
		plots = []
		for probe in probes:
			balance = [probe]

			r = s.get(url + str(probe))

			# Parse html
			soup = BeautifulSoup(r.text, "html.parser")
			value_div = soup.find("div", {"class": "value"})

			balance.append(value_div.text.strip('\t\n\r'))

			balances.append(balance)

			if request.POST.get('get-data'):

				# Get data files

				# Get input of start time and end time -> Needs correct ISO 8601 formatting
				# Get experiment start time
				with open(expt_pickle, 'rb') as f:
					dtStart = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(pickle.load(f)[0]))
				#dtStart = '2020-09-02T14:48:55Z'
				dtEnd = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time()))

				headers = {
					"exportProbeDataToCsvFilters": f'{{"idProbe":{probe},"dtStart":"{dtStart}","dtEnd":"{dtEnd}"}}'
				}

				p = s.post("http://www.bker.io/api/p/exportProbeDataToCsv", headers=headers)

				balance_file = os.path.join(balance_dir, f"weight{probe}.csv")
				with open(balance_file, "w") as f:
					f.write(eval(p.text))

			balance_file = os.path.join(balance_dir, f"weight{probe}.csv")

			if os.path.isfile(balance_file):

				with open(balance_file, 'r') as f:
					data = []
					start = None
					for line in f.readlines()[1:]:
						line = line.strip("\n").split("\t")
						line[1] = time.mktime(time.strptime(line[1], "%d/%m/%Y %H:%M:%S"))  # Time in seconds since epoch
						line[1] = line[1] / 3600
						line[2] = float(".".join(line[2].split(",")))  # Weight
						data.append(line[1:])
				data = np.array(data)
				data = data[data[:, 0].argsort()]  # Sort data using time and maintaining 'key' : 'value' structure

				data[:, 0] -= data[0, 0]

				p = figure(plot_width=400, plot_height=300)
				#p.y_range = Range1d(-.05, 1000)
				p.xaxis.axis_label = 'Time (h)'
				p.yaxis.axis_label = 'Weight (g)'
				p.line(data[:, 0], data[:, 1], line_width=1)

				plots.append(p)

	# show the results
	plot_script, plot_div = components(vplot(*plots))

	if not plots:
		plot_div = None

	last_updated = time.strftime("%a %d %b %Y %H:%M:%S", time.localtime())

	context = {
	"sidebar_links": sidebar_links,
	"experiment": experiment,
	"vial_count": vial_count,
	"balances": balances,
	"last_updated": last_updated,
	"plot_script": plot_script,
	"plot_div": plot_div
	}
	return render(request, "bker.html", context)


def file_scan(tag):
	rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
	evolver_dir = os.path.join(rootdir, "experiment")
	url_string = '{%s url "home" %s}' % ('%','%')

	sidebar_links =[]
	subdir_log = []

	for subdir in next(os.walk(evolver_dir))[1]:
		subdirname = os.path.join(next(os.walk(evolver_dir))[0], subdir)

		for subsubdir in next(os.walk(subdirname))[1]:
			if tag in subsubdir:
				#add_string = "<li><a href='%s'>%s</a></li>" % (url_string,subsubdir)
				sidebar_links.append(subsubdir)
				subdir_log.append(subdir)
				subdir_log.append(subdir)

	return sidebar_links,subdir_log
