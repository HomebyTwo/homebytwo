# Home by Two

This repository contains the Django source code for http://homebytwo.ch.
Home by two is a hobby project to improve the planning of hiking, running and cycling outings, so that I can reliably tell my wife at what time I will return home.

I'm hoping to find other young fathers with a similar motivation to contribute.

I am not really a web developer as you can probably tell. Enjoy!

Installation Requirements

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
- SWITZERLAN_MOBILITY_USERNAME:
- SWITZERLAN_MOBILITY_PASSWORD:


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