import leaflet from 'leaflet';


export default class LeafletMap extends HTMLElement {
  static get ROUTE_COLOR() {
    return '#cc0605';
  }

  static get ROUTE_WEIGHT() {
    return 4;
  }

  static getSwissMapBoundingBox() {
    return leaflet.latLngBounds(leaflet.latLng(45.398181, 5.140242), leaflet.latLng(48.230651, 11.47757));
  }

  connectedCallback() {
    const map = leaflet.map(this.getAttribute("map-id"));
    this.markers = leaflet.featureGroup();
    this.map = map;
  }

  // TODO move this to a new `marker` element
  updatePlaces(action, places) {

    // are we in edit mode?
    const isEdit = (action === 'edit');

    // save markers as feature group for easy disposal
    const newMarkers = this.leaflet.featureGroup();
    newMarkers.addTo(this.map);

    // prepare marker classes
    const markerClasses = {
      checkpoint: 'placeIcon--checkpoint',
      possible: 'placeIcon--possible',
      finish: 'placeIcon--finish',
      start: 'placeIcon--start'
    };

    places.forEach(place => {
      const isCheckpoint = (['checkpoint', 'possible'].includes(place.placeClass));
      const clickable = (isEdit && isCheckpoint);

      // Icon
      const checkpointIcon = this.leaflet.divIcon({className: `placeIcon ${markerClasses[place.placeClass]}`});

      // tooltip content
      const tooltipContent = `
        <div class="box box--tight text-center ">
          <h4 class="mrgv0">${place.schedule}</h4>
          <p class="mrgv0">${place.name}</p>
        </div>
      `;

      // create the marker and bind it as tooltip
      this.leaflet.marker([place.coords.lat, place.coords.lng], {icon: checkpointIcon})
        .addTo(newMarkers)
        .bindTooltip(tooltipContent)

        // add event listener to checkpoints
        .on('click', () => {
          if (clickable) {
            const checkpointsApp = window.HomeByTwo.Elm.checkpointsApp;
            checkpointsApp.ports.clickedPlace.send(place.id);
          }
        });
    });

    // dump previous markers and replace them with fresh batch
    this.markers.remove();
    this.markers = newMarkers;
  }
}

class Route extends HTMLElement {
  connectedCallback() {
    const leafletMapNode = this.parentElement;
    const map = leafletMapNode.map;
    const route = leaflet.geoJson(JSON.parse(this.getAttribute("geojson")), {
      style: {color: LeafletMap.ROUTE_COLOR, weight: LeafletMap.ROUTE_WEIGHT}
    });

    if (LeafletMap.getSwissMapBoundingBox().contains(route.getBounds())) {
      map.options.crs = leaflet.CRS.EPSG2056;
      const greyTopoLayer = leaflet.tileLayer.swiss({layer: 'ch.swisstopo.pixelkarte-grau'});
      const colorTopoLayer = leaflet.tileLayer.swiss().addTo(map);
      const baseMaps = {
        'Swiss Map': colorTopoLayer,
        'Swiss Map in grey': greyTopoLayer,
      };
      leaflet.control.layers(baseMaps, {}).addTo(map);
    } else {
      // TODO I don’t think this should belong to route
      leaflet.tileLayer(leafletMapNode.getAttribute("tile-url"), {
        attribution: '© <a href="https://www.mapbox.com/feedback/">Mapbox</a> © <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        tileSize: 512,
        zoomOffset: -1,
      }).addTo(map);
    }
    route.addTo(map);
    map.fitBounds(route.getBounds());
  }
  
}

customElements.define('leaflet-map', LeafletMap);
customElements.define('leaflet-route', Route);
