'use strict';

module.exports = {
  src: {
    sass:           'assets/stylesheets/**/*.scss',
    images:         'homebytwo/static/images/**/*.{gif,jpg,jpeg,png,svg}',
    javascripts:    'assets/javascripts/src/**/*.{js,jsx}',
    templates:      '**/*.html',
    icons:          'assets/icons/*.svg'
  },
  dest: {
    css:            'homebytwo/static/stylesheets',
    images:         'homebytwo/static/images'
  },
  browserSync: {
    proxy:          'homebytwo.lo',
    open:           false,
    notify:         false
  },
  sass: {
    outputStyle:    'compressed'
  },
  autoprefixer: {
    cascade:        false
  }
};
