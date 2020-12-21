export default class LeafletMap {
  static get ROUTE_COLOR() {
    return '#cc0605';
  }

  static get ROUTE_WEIGHT() {
    return 4;
  }

  static getSwissMapBoundingBox(leaflet) {
    return leaflet.latLngBounds(leaflet.latLng(45.398181, 5.140242), leaflet.latLng(48.230651, 11.47757));
  }

  constructor(leaflet, config, disabledServices = []) {

    const map = leaflet.map(config.id);
    this.leaflet = leaflet;
    this.markers = leaflet.featureGroup();

    disabledServices.forEach(service => map[service].disable());

    const route = leaflet.geoJson(config.routeGeoJson, {
      style: {color: LeafletMap.ROUTE_COLOR, weight: LeafletMap.ROUTE_WEIGHT}
    });
    if (LeafletMap.getSwissMapBoundingBox(leaflet).contains(route.getBounds())) {
      map.options.crs = leaflet.CRS.EPSG2056;
      const greyTopoLayer = leaflet.tileLayer.swiss({layer: 'ch.swisstopo.pixelkarte-grau'});
      const colorTopoLayer = leaflet.tileLayer.swiss().addTo(map);
      const baseMaps = {
        'Swiss Map': colorTopoLayer,
        'Swiss Map in grey': greyTopoLayer,
      };
      leaflet.control.layers(baseMaps, {}).addTo(map);
    } else {
      leaflet.tileLayer(config.mapBoxTileUrl, {
        attribution: '© <a href="https://www.mapbox.com/feedback/">Mapbox</a> © <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        tileSize: 512,
        zoomOffset: -1,
      }).addTo(map);
    }
    route.addTo(map);
    map.fitBounds(route.getBounds());
    this.map = map;
  }

  updatePlaces(places) {

    // save markers as feature group for easy disposal
    const newMarkers = this.leaflet.featureGroup();
    newMarkers.addTo(this.map);

    // prepare marker classes
    const markerClasses = {
      checkpoint: 'placeIcon--checkpoint',
      finish: 'placeIcon--finish',
      start: 'placeIcon--start'
    };

    places.forEach(place => {
      // Icon style
      let classes = `placeIcon ${markerClasses[place.placeClass]}`;
      classes += place.selected ? ' selected' : '';
      const checkpointIcon = this.leaflet.divIcon({className: classes});

      // tooltip content
      const tooltipContent = `
        <div class="box box--tight text-center ">
          <h4 class="mrgv0">${place.schedule}</h4>
          <p class="mrgv0">${place.name}</p>
        </div>
      `;

      // create the marker and bind it as tooltip
      const marker = this.leaflet.marker(
        [place.coords.lat, place.coords.lng], {icon: checkpointIcon})
        .addTo(newMarkers)
        .bindTooltip(tooltipContent);

      // add event listener to editable places
      if (place.edit) {
        marker.on('click', () => {
          const checkpointsApp = window.HomeByTwo.Elm.checkpointsApp;
          checkpointsApp.ports.clickedPlace.send(
            {'placeId': place.id, 'placeClass': place.placeClass}
          );
        });
      }
    });

    // dump previous markers and replace them with fresh batch
    this.markers.remove();
    this.markers = newMarkers;
  }
}


