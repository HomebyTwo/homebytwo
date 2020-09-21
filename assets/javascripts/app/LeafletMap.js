export default class LeafletMap {
  static get ROUTE_COLOR() {
    return 'red';
  }

  static get POINT_COLOR() {
    return 'black';
  }

  constructor(leaflet, config, disabledServices = []) {
    const map = leaflet.map(config.id, { crs: leaflet.CRS.EPSG2056 });

    const route = leaflet.geoJson(config.routeGeoJson, {
      style: { color: LeafletMap.ROUTE_COLOR }
    });
    route.addTo(map);
    map.fitBounds(route.getBounds());

    disabledServices.forEach(service => map[service].disable());

    // Add Swiss layer with default options
    leaflet.tileLayer.swiss().addTo(map);

    const icon = L.divIcon({ className: config.divIconClassName });
    document.querySelectorAll(config.markersSelector).forEach(place => {
      leaflet.geoJson(JSON.parse(place.dataset.geom), {
        pointToLayer: (feature, latlng) => leaflet.marker(latlng, {
          icon: icon,
          title: feature.properties.name
        }),
        style: { color: LeafletMap.POINT_COLOR },
        onEachFeature: (feature, layer) => layer.bindPopup(feature.properties.name)
      }).addTo(map);
    });
  }
}
