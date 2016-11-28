'use strict';

module.exports = {
  src: {
    sass:           'static/sass/**/*.scss',
    javascripts:    'static/javascripts/src/**/*.{js,jsx}',
    webpack:        ['./static/javascripts/src/main.js'],
    images:         'static/images/**/*.{gif,jpg,jpeg,png,svg}',
    templates:      '**/*.html'
  },
  dest: {
    css:            'static/stylesheets',
    webpack:        { path: './static/javascripts/', filename: 'main.js' },
    images:         'static/images'
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
    browsers:       ['last 2 versions', 'ie 9'],
    cascade:        false
  }
};
