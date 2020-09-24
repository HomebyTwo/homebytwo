export default class LeafletMap {
  static get ROUTE_COLOR() {
    return '#cc0605';
  }

  static get ROUTE_WEIGHT() {
    return 4;
  }

  constructor(leaflet, config, disabledServices = []) {
    const map = leaflet.map(config.id, {crs: leaflet.CRS.EPSG21781});

    const route = leaflet.geoJson(config.routeGeoJson, {
      style: {color: LeafletMap.ROUTE_COLOR, weight: LeafletMap.ROUTE_WEIGHT}
    });
    route.addTo(map);
    map.fitBounds(route.getBounds());

    disabledServices.forEach(service => map[service].disable());

    // Add Swiss layer with default options
    leaflet.tileLayer.swiss({layer: 'ch.swisstopo.pixelkarte-grau', crs: leaflet.CRS.EPSG21781}).addTo(map);

    const icon = L.divIcon({className: config.divIconClassName});
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
