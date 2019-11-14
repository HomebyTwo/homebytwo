// Import the main Sass file
import 'stylesheets/homebytwo.scss';

// UI
import 'ui/icons';

import Vue from 'vue';
import Vuex from 'vuex';

import store from './store/store.js';

import PlacesList from './components/PlacesList.vue';

Vue.use(Vuex);

Vue.component('places-list', PlacesList);

new Vue({
  el: '#places-list',
  store: new Vuex.Store(store)
});
