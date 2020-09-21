/* eslint-env node */
const path = require('path');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const SpriteLoaderPlugin = require('svg-sprite-loader/plugin');
const browserslist = require('./package.json').browserslist;
const VueLoaderPlugin = require('vue-loader/lib/plugin');

module.exports = {
  mode: process.env.NODE_ENV,
  resolve: {
    modules: [
      path.resolve(__dirname, 'assets/javascripts'),
      path.resolve(__dirname, 'assets'),
      'node_modules',
    ],
    extensions: ['.js', '.vue'],
    alias: {
      vue$: 'vue/dist/vue.esm.js',
    },

  },
  entry: {
    main: path.resolve(__dirname, 'assets/javascripts/main.js'),
  },
  output: {
    path: path.resolve(__dirname, 'homebytwo/static/assets'),
    filename: '[name].js',
  },
  module: {
    rules: [
      {
        test: /\.vue$/,
        loader: 'vue-loader',
      },
      {
        test: /\.js$/,
        include: path.resolve(__dirname, 'assets/javascripts'),
        exclude: /node_modules/,
        loader: 'babel-loader',
      },
      {
        test: /\.scss$/,
        use: [
          {
            loader: process.env.NODE_ENV === 'production' ? MiniCssExtractPlugin.loader : 'style-loader',
          },
          'css-loader',
          {
            loader: 'postcss-loader',
            options: {
              plugins: [
                require('autoprefixer')(),
                require('cssnano')(),
              ],
            },
          },
          'sass-loader',
        ],
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader']
      },
      {
        test: /\.(svg|png|jpe?g|gif|webp|woff|woff2|eot|ttf|otf)$/,
        exclude: path.resolve('./assets/icons'),
        use: [
          {
            loader: 'file-loader',
            options: {
              name: '[name].[ext]',
              outputPath: 'homebytwo/static/images',
            },
          },
        ],
      },
      {
        test: /\.svg$/,
        include: path.resolve('./assets/icons'),
        use: [
          {
            loader: 'svg-sprite-loader',
            options: {
              extract: true,
              spriteFilename: 'icons.svg',
              esModule: false,
            },
          },
          'svgo-loader',
        ],
      },
    ],
  },
  plugins: [
    new MiniCssExtractPlugin({
      filename: '[name].css',
    }),
    new SpriteLoaderPlugin(),
    new VueLoaderPlugin(),
  ],
  devServer: {
    proxy: {
      '**': 'http://local.homebytwo.ch',
    },
    public: 'local.homebytwo.ch:3000',
    host: '0.0.0.0',
    port: 3000,
    compress: true,
    // Polling is required inside Vagrant boxes
    watchOptions: {
      poll: true,
    },
    overlay: true,
    // Here you can specify folders that contain your views
    // So they’ll trigger a page reload when you change them
    contentBase: ['./homebytwo/templates/'],
    publicPath: '/static/assets/',
    watchContentBase: true,
  },
};
