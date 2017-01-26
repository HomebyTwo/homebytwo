# Home by Two  [![Build Status](https://travis-ci.org/HomebyTwo/homebytwo.svg?branch=master)](https://travis-ci.org/HomebyTwo/homebytwo)

This repository contains the Django source code for http://homebytwo.ch.
Home by two is a hobby project to plan the schedule of hiking, running and cycling outings, in order to reliably tell what time I will be back.

It would be great if other young fathers with a similar motivation could contribute to the vision.


## Installation Requirements

```
Vagrant >= 1.8.4
Git >= 1.0
```

You also need a virtualization solution, either one of these:

```
Virtualbox >= 4.3
LXC >= 1.0 & vagrant-lxc >= 1.0.0.alpha.2
```

Optional dependencies:

- vagrant-hostmanager A Vagrant plugin that manages /etc/hosts files. (will be automatically used if installed, make sure it's at least 1.5.0 if you have it)



## Installation

Clone the repository on your machine and open the project directory:

```sh
$ git clone --recursive https://github.com/drixselecta/homebytwo.git && cd homebytwo
```

Insall addition vagrant plugins:

```sh
$ vagrant plugin install vagrant-cachier vagrant-hostmanager
```

Create and provision the virtual machine:

```sh
$ vagrant up
```

Add API setting files to envdir:
- GOOGLEMAPS_API_KEY:
- MAPBOX_ACCESS_TOKEN:
- OPENTRANSPORTDATA_API_KEY:
- STRAVA_CLIENT_ID:
- STRAVA_SECRET:
- SWISS_PUBLIC_TRANSPORT_API_URL:


## Run the development server:

```sh
$ vagrant ssh
$ ./manage.py runserver
```

Open Home by two in your browser:

http://homebytwo.lo


## Create superuser

To create an initial user, you can user the create superuser function.

```
$ ./manage.py createsuperuser
```


## Run Tests

```sh
$ vagrant ssh
$ tox
```


## Import Places from SwissNAME3D

Dowload the shapefile from [opendata.swiss](https://opendata.swiss/en/dataset/swissnames3d-geografische-namen-der-landesvermessung1), the file is about 390.21M:

```sh
$ vagrant ssh
$ wget -O /tmp/data.zip http://data.geo.admin.ch/ch.swisstopo.swissnames3d/data.zip && cd /tmp
```

Unzip the data twice and move it to the media folder:

```sh
$ unzip data.zip swissNAMES3D_LV03.zip
$ unzip swissNAMES3D_LV03.zip swissNAMES3D_LV03/shp_LV03_LN02/swissNAMES3D_PKT.*
$ mkdir -p /vagrant/media/shapefiles && mv swissNAMES3D_LV03/shp_LV03_LN02/swissNAMES3D_PKT.* /vagrant/media/shapefiles/
```

Cleanup and go back to the project root:

```
$ rm -rf data.zip swissNAMES3D_LV03.zip swissNAMES3D_LV03 && cd /vagrant/
```

Run the importer command:

```sh
$ ./manage.py importswissname3d media/shapefiles/swissNAMES3D_PKT.shp
```