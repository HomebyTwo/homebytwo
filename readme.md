# Home by Two  [![Build Status](https://travis-ci.org/drixselecta/homebytwo.svg?branch=master)](https://travis-ci.org/drixselecta/homebytwo)

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

## SSH into the box and run the development server:

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
$ tox
```
