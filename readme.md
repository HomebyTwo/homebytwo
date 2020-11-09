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
- `STRAVA_VERIFY_TOKEN` - The token configured to receive updates from the Strava Webhook Events API. More info at https://developers.strava.com/docs/webhooks/

## Run the development server:

```sh
$ vagrant ssh
$ ./manage.py runserver
```

Open Home by two in your browser:

http://local.homebytwo.ch


## Create superuser

To create an initial user, you can user the create superuser function.

```
$ ./manage.py createsuperuser
```

## Import Places from SwissNAMES3D or geonames.org

In order to find places along routes, homebytwo requires places in the database.

For Switzerland, places should be imported from [SwissNAMES3D](https://opendata.swiss/en/dataset/swissnames3d-geografische-namen-der-landesvermessung).
The import of more than 300.000 places takes about 30 minutes:

```sh
$ ./manage.py import_swissnames3d_places
```

Thanks to [geonames.org](https://www.geonames.org), you can also places from other countries:

```sh
$ ./manage.py import_geonames_places ES FR DE IT
```


## Run Tests

```sh
$ vagrant ssh
$ tox
```

## Add a requirement

Add the requirement to the `requirements/xxx.in` file, and then run `make requirements` (from inside the box) to update
the `.txt` files and install the requirement(s) in the virtual environment.


## Managing Celery

After changing a task code, you'll need to restart Celery for changes to be taken into account (Celery is run asynchronously because some processes take a really long time, including the signup process which would otherwise timeout). To restart celery, run:

```
sudo systemctl restart celery
```

To see the output of Celery tasks, use `journalctl` (`-f` is to follow the output):

```
sudo journalctl -u celery -f
```
