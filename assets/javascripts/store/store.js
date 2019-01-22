import axios from 'axios';

export default {
  state: {
    places: [],
    checkpoints: {},
  },
  mutations: {
    'FETCH_PLACES_SUCCESS'(state, places) {
      state.places = places;
    }
  },
  actions: {
    fetchPlaces({commit, state}, routeId) {
      if (state.places.length > 0) {
        return;
      }
      axios.get(`/import/api/switzerland-mobility/${routeId}`)
        .then(response => {
          let {data} = response;
          data = data.map(place => {
            return { code: place[0], name: place[1] };
          });
          commit('FETCH_PLACES_SUCCESS', data);
        });
    }
  }
};