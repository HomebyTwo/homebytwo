# Change Log
## [0.6.0] - 2019-11-13 Retrieve Activities from Strava
- An athlete's Strava activities can be retrieved and saved to the database
- Strava Webhook API subscriptions can be authorized
- Events sent from the Strava Webhook API subscriptions are saved to the database (but not yet processed)

## [0.5.2] - 2019-11-04 Adapt to Strava API changes
- The Strava API now uses refresh tokens and does not discloses email addresses

## [0.5.1] - 2018-08-31 Distinguish local from more important places
- SwissNAME3D has added a lot of unimportant local places. We want to filter them more efficiently, so we need to distinguish them from the real thing.

## [0.5.0] - 2018-08-30 Filter proposed checkpoints by type
### Added
- You can now choose the type of checkpoints found when importing a new route.
- No bus stations are proposed for Bike routes

## [0.4.2] - 2018-08-19 Cleanup HDf files
### Added
- New management command to cleanup old HDF files used to store route data

## [0.4.0] - 2018-08-18 Link to source on route page
### Added
- On the route page, display a link to the original route on Strava or Switzerland Mobility

## [0.3.0] - 2018-05-16 Athlete Registration
### Added
- Django Social Auth registration with the Strava Backend
- Homebytwo registration

### Changed
- Connect with Strava always uses Django Social Auth

## [0.2.4] - 2018-05-13 Messages
### Changed
- Use messages instead of a custom solution to display notifications

## [0.2.3] - 2018-05-11 Upgrade Kanbasu to version 2
### Added
- Use SVG icons from a sprite generated automagically

### Changed
- adapt forms to use Kanbasu form classes
- provide a generic form template

## [0.2.2] - 2018-05-08 Cleanup old requirements
### fixed
- remove Google Maps Module
- fix deployment restart process

## [0.2.1] - 2018-05-07 Two Scoops refactor
### fixed
- fix imports and flake8 errors
- rearrange file layout to somewhat match two scoops recommendations
- get custom fields out of the models
- Add TimeStampedModel AbstractClass and use it

## [0.2.0] - 2018-04-04 Individual Performance
### Added
- Calculate Schedule based on athlete performance \o/ 

## [0.1.5] - 2018-02-12 Pitch Pimp
### Changed
- Pimp up the landing page pitch

## [0.1.x] - 2018-07-04 Import Routes
### Added
- Import routes from Strava and Switzerland Mobility Plus

## [0.0.x] - 2018-07-04 Import places from SwissNAME3D
### Added
- use a command to load places from SwissNAME3d shapefile

## [0.0.1] - 2016-12-04 First blood

### Added
- Initial prototype version with a lot of work to do!
