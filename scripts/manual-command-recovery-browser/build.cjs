const path = require('path');
const root = path.resolve(__dirname, '../..');
const modules = path.join(root, 'node_modules');
const webpack = require(path.join(modules, 'webpack'));
process.env.NODE_ENV = 'production';

if (!process.argv[2]) throw new Error('Pass the temporary output directory');
webpack({
  mode:'production',devtool:false,entry:path.join(__dirname,'harness.jsx'),
  output:{path:path.resolve(process.argv[2]),filename:'bundle.js'},
  resolve:{modules:[modules,'node_modules'],extensions:['.js','.jsx']},
  plugins:[new webpack.DefinePlugin({
    'process.env.REACT_APP_API_URL':JSON.stringify('/api'),
    'process.env.REACT_APP_CLIENT_ERROR_LOGGING':JSON.stringify('false'),
  })],
  module:{rules:[{test:/\.(js|jsx)$/,exclude:/node_modules/,use:{
    loader:path.join(modules,'babel-loader'),
    options:{babelrc:false,configFile:false,presets:[[
      path.join(modules,'babel-preset-react-app'),{runtime:'automatic'},
    ]]},
  }}]},
}, (error,stats) => {
  if (error || stats.hasErrors()) {
    console.error(error || stats.toString({all:false,errors:true}));
    process.exitCode = 1;
  } else console.log('Manual recovery browser fixture compiled');
});
