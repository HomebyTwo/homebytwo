# Home by Two

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

Clone the repository on your machine:

```sh
$ git clone --recursive https://github.com/drixselecta/homebytwo.git
```

Insall addition vagrant plugins:

```sh
$ vagrant plugin install vagrant-cachier vagrant-hostmanager
```

Create and provision the virtual machine:

```sh
$ vagrant up
```

Add setting files to envdir:
- ALLOWED_HOSTS:
- GOOGLEMAPS_API_KEY:
- MAPBOX_ACCESS_TOKEN:
- OPENTRANSPORTDATA_API_KEY:
- STRAVA_CLIENT_ID:
- STRAVA_SECRET:
- SWISS_PUBLIC_TRANSPORT_API_URL:


Open Home by two:

http://homebytwo.lo

## SSH into the box:

```
$ vagrant ssh
```

## Create superuser

```
$ ./manage.py createsuperuser
```