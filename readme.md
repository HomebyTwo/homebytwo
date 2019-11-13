# Home by Two  [![Build Status](https://travis-ci.org/HomebyTwo/homebytwo.svg?branch=master)](https://travis-ci.org/HomebyTwo/homebytwo) [![Coverage Status](https://coveralls.io/repos/github/HomebyTwo/homebytwo/badge.svg?branch=master)](https://coveralls.io/github/HomebyTwo/homebytwo?branch=master)

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
$ git clone --recursive https://github.com/HomebyTwo/homebytwo.git && cd homebytwo
```

Insall addition vagrant plugins:

```sh
$ vagrant plugin install vagrant-cachier vagrant-hostmanager
```

Create and provision the virtual machine:

```sh
$ vagrant up
```

Add the following setting files to the envdir folder containing the corresponding value for the environment variable:
- `MAILCHIMP_API_KEY` - Available at https://us14.admin.mailchimp.com/account/api/
- `MAILCHIMP_LIST_ID` - The ID of the Mailchimp list that ne1wsletter subscriber should be added to
- `MAPBOX_ACCESS_TOKEN` - retrieve it at https://www.mapbox.com/account/access-tokens
- `STRAVA_CLIENT_ID` your Strava client ID available at https://www.strava.com/settings/api
- `STRAVA_CLIENT_SECRET` - your Strava secret available at https://www.strava.com/settings/api
- `STRAVA_ROUTE_URL` - set it to `https://www.strava.com/routes/%d`
- `STRAVA_VERIFY_TOKEN` - The token configured to receive updates from the Strava Webhook Events API
- `SWITZERLAND_MOBILITY_LIST_URL` - set it to `https://map.wanderland.ch/api/4/tracks_list`
- `SWITZERLAND_MOBILITY_LOGIN_URL` - set it to `https://map.schweizmobil-hosting.ch/api/4/login`
- `SWITZERLAND_MOBILITY_ROUTE_URL` - set it to `https://map.wanderland.ch/?trackId=%d`
- `SWITZERLAND_MOBILITY_ROUTE_DATA_URL` - set it to `https://map.wanderland.ch/track/%d/show`


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

Dowload the shapefile from [opendata.swiss](https://opendata.swiss/en/dataset/swissnames3d-geografische-namen-der-landesvermessung), the file is about 390.21M:

```sh
$ vagrant ssh
$ wget -O /tmp/data.zip http://data.geo.admin.ch/ch.swisstopo.swissnames3d/data.zip && cd /tmp
```

Unzip the data twice and move it to the media folder:

```sh
$ unzip data.zip swissNAMES3D_LV03.zip
$ unzip swissNAMES3D_LV03.zip swissNAMES3D_LV03/shp_LV03_LN02/swissNAMES3D_PKT.*
$ mkdir -p /vagrant/homebytwo/media/shapefiles && mv swissNAMES3D_LV03/shp_LV03_LN02/swissNAMES3D_PKT.* /vagrant/homebytwo/media/shapefiles/
```

Cleanup and go back to the project root:

```
$ rm -rf data.zip swissNAMES3D_LV03.zip swissNAMES3D_LV03 && cd /vagrant/
```

Run the importer command:

```sh
$ ./manage.py importswissname3d homebytwo/media/shapefiles/swissNAMES3D_PKT.shp
```