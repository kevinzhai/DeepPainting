import flask
import json
import os
import time
import test_cyclegan as cgan
import numpy as np
from skimage.io import imsave
from skimage.transform import resize
from PIL import Image, ImageFile
from gevent.event import AsyncResult, Timeout
from gevent.queue import Empty, Queue
from shutil import rmtree
from hashlib import sha1
from stat import S_ISREG, ST_CTIME, ST_MODE


DATA_DIR = 'demo_data'
KEEP_ALIVE_DELAY = 25
MAX_IMAGE_SIZE = 800, 600
MAX_IMAGES = 20
MAX_DURATION = 300
MAX_DIFF = 1.25
IMAGE_PADDING = 7
MODEL = "cubism_v1"

app = flask.Flask(__name__, static_folder=DATA_DIR)
broadcast_queue = Queue()


#try:  # Reset saved files on each start
 #   rmtree(DATA_DIR, True)
  #  os.mkdir(DATA_DIR)
#except OSError:
  #  pass


def broadcast(message):
    """Notify all waiting waiting gthreads of message."""
    waiting = []
    try:
        while True:
            waiting.append(broadcast_queue.get(block=False))
    except Empty:
        pass
    print('Broadcasting {0} messages'.format(len(waiting)))
    for item in waiting:
        item.set(message)


def receive():
    """Generator that yields a message at least every KEEP_ALIVE_DELAY seconds.
    yields messages sent by `broadcast`.
    """
    now = time.time()
    end = now + MAX_DURATION
    tmp = None
    # Heroku doesn't notify when client disconnect so we have to impose a
    # maximum connection duration.
    while now < end:
        if not tmp:
            tmp = AsyncResult()
            broadcast_queue.put(tmp)
        try:
            yield tmp.get(timeout=KEEP_ALIVE_DELAY)
            tmp = None
        except Timeout:
            yield ''
        now = time.time()


def safe_addr(ip_addr):
    """Strip of the trailing two octets of the IP address."""
    return '.'.join(ip_addr.split('.')[:2] + ['xxx', 'xxx'])


def correct_image_ratio(img, ratio=1.5):
  """
  corrects the aspect ratio of the image if it is too extreme
  """
  h, w, c = img.shape
  if max(h, w) / min(h, w) > ratio:
    if h > w:
      center = round(h / 2)
      height = ratio * w
      img = img[round(center - height/2):round(center + height/2), :, :]
    elif False:
      center = round(w / 2)
      width = ratio * h
      img = img[:, round(center - width/2):round(center + width/2), :]
      pass
  return img


def save_normalized_image(path, data):
    image_parser = ImageFile.Parser()
    try:
        image_parser.feed(data)
        image = image_parser.close()
    except IOError:
        raise
        return False
    image.thumbnail(MAX_IMAGE_SIZE, Image.ANTIALIAS)
    if image.mode != 'RGB':
        image = image.convert('RGB')

    image_np = np.array(image)
    image_np = correct_image_ratio(image_np, ratio=MAX_DIFF)

    opts = cgan.create_options(MODEL, epoch=200)
    print(image_np.shape)
    image_stylized = cgan.test(image_np, opts) / 255.0
    image_original_resize = resize(image_np, image_stylized.shape)
    padding = np.zeros((image_stylized.shape[0], IMAGE_PADDING, 3))

    # print("STYLIZED IMAGE......", image_stylized.shape, image_stylized)
    # print("ORIGINAL RESIZED IMAGE........", image_original_resize.shape, image_original_resize)
    combined_img = np.concatenate([image_stylized, padding, image_original_resize], 1)

    imsave(path, combined_img)
    return True


def event_stream(client):
    force_disconnect = False
    try:
        for message in receive():
            yield 'data: {0}\n\n'.format(message)
        print('{0} force closing stream'.format(client))
        force_disconnect = True
    finally:
        if not force_disconnect:
            print('{0} disconnected from stream'.format(client))


@app.route('/post', methods=['POST'])
def post():
    sha1sum = sha1(flask.request.data).hexdigest()
    target = os.path.join(DATA_DIR, '{0}.jpg'.format(sha1sum))
    message = json.dumps({'src': target,
                          'ip_addr': safe_addr(flask.request.access_route[0])})
    try:
        if save_normalized_image(target, flask.request.data):
            broadcast(message)  # Notify subscribers of completion
    except Exception as e:  # Output errors
        return '{0}'.format(e)
    return 'success'


@app.route('/stream')
def stream():
    return flask.Response(event_stream(flask.request.access_route[0]),
                          mimetype='text/event-stream')


@app.route('/')
def home():
    # Code adapted from: http://stackoverflow.com/questions/168409/
    image_infos = []
    for filename in os.listdir(DATA_DIR):
        filepath = os.path.join(DATA_DIR, filename)
        file_stat = os.stat(filepath)
        if S_ISREG(file_stat[ST_MODE]):
            image_infos.append((file_stat[ST_CTIME], filepath))

    images = []
    for i, (_, path) in enumerate(sorted(image_infos, reverse=True)):
        if i >= MAX_IMAGES:
            os.unlink(path)
            continue
        images.append('<div id="images"><img alt="User uploaded image" src="{0}" /></div>'
.format(path))
    print(image_infos)
    return """
<!doctype html>
<title>GAN Style Transfer Demo</title>
<meta charset="utf-8" />
<script src="//ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js"></script>
<script src="//ajax.googleapis.com/ajax/libs/jqueryui/1.10.1/jquery-ui.min.js"></script>
<link rel="stylesheet" href="//ajax.googleapis.com/ajax/libs/jqueryui/1.10.1/themes/vader/jquery-ui.css" />
<link href="https://fonts.googleapis.com/css?family=Open+Sans" rel="stylesheet"> 
<style>
  body {
    max-width: 1100px;
    margin: auto;
    padding: 1em;
    background: black;
    color: #fff;
    font: 16px/1.6 menlo, monospace;
    font-family: 'Open Sans', sans-serif;
    text-align:center;
  }
  a {
    color: #fff;
  }
  .notice {
    font-size: 80%%;
  }
#drop {
    font-weight: bold;
    text-align: center;
    padding: 1em 0;
    margin: 1em 0;
    color: #555;
    border: 2px dashed #555;
    border-radius: 7px;
    cursor: default;
}
#drop.hover {
    color: #f00;
    border-color: #f00;
    border-style: solid;
    box-shadow: inset 0 3px 4px #888;
}

h2 {
    font-size: 40px;
    font-weight: light;
}
</style>
<h2>Genre-tive Artistic Networks: Style Transfer Demo</h2>
<p>Upload an image or take a picture with your phone to stylize it as a Cubist painting. The most recent %s images are displayed publicly. <br> Note: Portrait oriented images may not process correctly, opt for the Landscape orientation if possible. </p>

<noscript>Note: You must have javascript enabled in order to upload and
dynamically view new images.</noscript>
<fieldset>
  <p id="status">Select an image</p>
  <div id="progressbar"></div>
  <input id="file" type="file" />
  <div id="drop">or drop image here</div>
</fieldset>
<h3>Stylized Images (updated in real-time)</h3>
<div id="images">%s</div>
<script>
  function sse() {
      var source = new EventSource('/stream');
      source.onmessage = function(e) {
          if (e.data == '')
              return;
          var data = $.parseJSON(e.data);
          var upload_message = 'Image uploaded by ' + data['ip_addr'];
          var image = $('<img>', {alt: upload_message, src: data['src']});
          var container = $('<div>').hide();
          container.append($('<div>', {text: upload_message}));
          container.append(image);
          $('#images').prepend(container);
          image.load(function(){
              container.show('blind', {}, 1000);
          });
      };
  }
  function file_select_handler(to_upload) {
      var progressbar = $('#progressbar');
      var status = $('#status');
      var xhr = new XMLHttpRequest();
      xhr.upload.addEventListener('loadstart', function(e1){
          status.text('uploading image');
          progressbar.progressbar({max: e1.total});
      });
      xhr.upload.addEventListener('progress', function(e1){
          if (progressbar.progressbar('option', 'max') == 0)
              progressbar.progressbar('option', 'max', e1.total);
          progressbar.progressbar('value', e1.loaded);
      });
      xhr.onreadystatechange = function(e1) {
          if (this.readyState == 4)  {
              if (this.status == 200)
                  var text = 'upload complete: ' + this.responseText;
              else
                  var text = 'upload failed: code ' + this.status;
              status.html(text + '<br/>Select an image');
              progressbar.progressbar('destroy');
          }
      };
      xhr.open('POST', '/post', true);
      xhr.send(to_upload);
  };
  function handle_hover(e) {
      e.originalEvent.stopPropagation();
      e.originalEvent.preventDefault();
      e.target.className = (e.type == 'dragleave' || e.type == 'drop') ? '' : 'hover';
  }
  $('#drop').bind('drop', function(e) {
      handle_hover(e);
      if (e.originalEvent.dataTransfer.files.length < 1) {
          return;
      }
      file_select_handler(e.originalEvent.dataTransfer.files[0]);
      
  }).bind('dragenter dragleave dragover', handle_hover);
  $('#file').change(function(e){
      file_select_handler(e.target.files[0]);
      e.target.value = '';
  });
  sse();
  var _gaq = _gaq || [];
  _gaq.push(['_setAccount', 'UA-510348-17']);
  _gaq.push(['_trackPageview']);
  (function() {
    var ga = document.createElement('script'); ga.type = 'text/javascript'; ga.async = true;
    ga.src = ('https:' == document.location.protocol ? 'https://ssl' : 'http://www') + '.google-analytics.com/ga.js';
    var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(ga, s);
  })();
</script>
""" % (MAX_IMAGES, '\n'.join(images))


if __name__ == '__main__':
    app.debug = True
app.run('0.0.0.0', threaded=True)
