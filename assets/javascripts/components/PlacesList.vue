<template>
  <div class="mrgb box box--primary pdg-">
    <form method="get">
      <div class="form-group">
        <h2>Type of Checkpoints</h2>
        <label v-for="checkpoint in checkpoints" class="label label--inline">
          <input type="checkbox" :value="checkpoint.code"> {{ place.name }}
        </label>
        <button type="submit">Update Checkpoints</button>
      </div>
    </form>
  </div>
</template>

<script>
  import { mapState, mapActions } from 'vuex';
  import axios from 'axios';

  export default {
    props: ['routeId'],
    methods: {
       ...mapActions(['fetchPlaces'])
    },
    mounted() {
      this.fetchPlaces(this.routeId);
    },
    computed: {
      ...mapState(['places'])
    }
  }
</script>