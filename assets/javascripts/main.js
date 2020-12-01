// Import the main Sass file
import 'stylesheets/homebytwo.scss';

// UI
import 'ui/icons';

import '../../node_modules/leaflet/dist/leaflet.css';
import 'leaflet-tilelayer-swiss';

const HomeByTwo = {};

import L from 'leaflet';
HomeByTwo.L = L;

import LeafletMap from 'app/LeafletMap';
HomeByTwo.LeafletMap = LeafletMap;

Object.assign(window, { HomeByTwo });

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
