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

    const route = leaflet.geoJson(config.routeGeoJson, {
      style: {color: LeafletMap.ROUTE_COLOR, weight: LeafletMap.ROUTE_WEIGHT}
    });

    if (LeafletMap.getSwissMapBoundingBox(leaflet).contains(route.getBounds())) {
      map.options.crs = leaflet.CRS.EPSG2056;
      const greyTopoLayer = leaflet.tileLayer.swiss({layer: 'ch.swisstopo.pixelkarte-grau'}).addTo(map);
      const colorTopoLayer = leaflet.tileLayer.swiss();
      const baseMaps = {
        'Grey': greyTopoLayer,
        'Color': colorTopoLayer,
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

    disabledServices.forEach(service => map[service].disable());

    const icon = leaflet.divIcon({className: config.divIconClassName});
    document.querySelectorAll(config.markersSelector).forEach(place => {
      leaflet.geoJson(JSON.parse(place.dataset.geom), {
        pointToLayer: (feature, latlng) => leaflet.marker(latlng, {
          icon: icon,
          title: feature.properties.name
        }),
        style: {},
        onEachFeature: (feature, layer) => layer.bindPopup(feature.properties.name)
      }).addTo(map);
    });
  }
}
