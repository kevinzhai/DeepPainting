import os
import time
import numpy as np
import scipy
import random
import tqdm
import pandas as pd
import socket
import psutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from keras.optimizers import Adam
np.seterr(divide='ignore', invalid='ignore')

class ProjectConfig:
    basepath = '/home/ubuntu/DeepPainting/flickr-64-sample-3000'
    model_subdirectory = 'model3'
    if os.path.exists(os.path.join(basepath, model_subdirectory)):
        input("Model directory already exists. Are you sure you want to override? Press any ENTER to continue...")
    imsize = (64,) * 2  # n x n square images, VGG default is 224x224
    tsize = imsize + (3,)
    trainfolder = os.path.join(basepath, 'train')
    # Set test = train to overfit train data
    testfolder = os.path.join(basepath, 'test')


### additional parameters
img_extension = '.jpg'
train_samples_per_class = 2000
test_samples_per_class = 500
show_heatmap = True
show_conv_filters = False
gpu_fraction = 1.0
###


# Model settings
cfg = ProjectConfig()
cfg.vgglayers = 2        # Number of VGG layers to create, 0-5 layers
# Enable transfer learning up to layer n (max 12, -1 = off)
cfg.xferlearning = -1
cfg.freeze_conv = False    # Freeze convolutional layers
cfg.fclayersize = 128      # Size of fully connected (FC) layers
cfg.fclayers = 2        # Number of FC layers
cfg.fcdropout = 0.4      # Dropout regularization factor for FC layers
cfg.l1 = 0.0      # L1 regularization for FC
cfg.l2 = 0.0      # L2 regularization for FC
# Random labels (remember to rename/delete existing data folder)
cfg.randomlbls = False

# Optimizer settings
optimizer = Adam(lr=.00001)
# Change for early stopping regularization
cfg.batch_size, cfg.nb_epoch = 32, 10000
cfg.batchnorm = False    # Batch normalization (incompatible with filter viz)
cfg.saveloadmodel = True     # Save/load models to reduce training time
cfg.spercls = train_samples_per_class     # Number of samples per class

# Visualization settings
cfg.hsv = False    # Convert images to Hue/Saturation/Value to be more robust to colors
# Decrease for speed, increase for better viz. 0 = off.
cfg.vizfilt_timeout = 0

# Model checkpointing/stats
os.makedirs(os.path.join(cfg.basepath, cfg.model_subdirectory), exist_ok=True)
os.makedirs(os.path.join(cfg.basepath, cfg.model_subdirectory, "loss"), exist_ok=True)
os.makedirs(os.path.join(cfg.basepath, cfg.model_subdirectory, "filters"), exist_ok=True)
print(os.path.join(os.path.join(cfg.basepath, cfg.model_subdirectory)))
cfg.modelarch = 'vgg%d-fcl%d-fcs%d-%s-%s' % (cfg.vgglayers, cfg.fclayers,
                                             cfg.fclayersize, 'hsv' if cfg.hsv else 'rgb', socket.gethostname())
cfg.modelid = os.path.join(cfg.basepath, cfg.model_subdirectory, 'model-%s.h5' % cfg.modelarch)
cfg.trainstats = os.path.join(
    cfg.basepath, cfg.model_subdirectory, 'trainstats-%s.csv' % cfg.modelarch)

#%% Image data augmentation
from keras.preprocessing.image import ImageDataGenerator
datagen = ImageDataGenerator(
    featurewise_center=False,               # set input mean to 0 over the dataset
    samplewise_center=False,                # set each sample mean to 0
    featurewise_std_normalization=False,    # divide inputs by std of the dataset
    samplewise_std_normalization=False,     # divide each input by its std
    zca_whitening=False,                    # apply ZCA whitening
    # randomly rotate images in the range (degrees, 0 to 180)
    rotation_range=0,
    # randomly shift images horizontally (fraction of total width)
    width_shift_range=0.0,
    # randomly shift images vertically (fraction of total height)
    height_shift_range=0.0,
    horizontal_flip=False,                  # randomly flip images
    vertical_flip=False)                    # randomly flip images
#%% ------ CPU/GPU memory fix -------
import tensorflow as tf
import keras.backend.tensorflow_backend as ktf


def get_session(gpu_fraction=gpu_fraction):
    gpu_options = tf.GPUOptions(
        per_process_gpu_memory_fraction=gpu_fraction, allow_growth=True)
    return tf.Session(config=tf.ConfigProto(gpu_options=gpu_options))
ktf.set_session(get_session())


def check_memusage():
    process = psutil.Process(os.getpid())
    pctused = 100 * process.memory_info().rss / psutil.virtual_memory().total
    if pctused > 50:
        print('**** High memory usage detected***')
        print('Please check your code for memory leaks. Percent memory used: ', pctused)
#%% Create demo data


def makedata(basepath):
    if os.path.exists(basepath):
        return
    from keras.datasets import cifar10
    (X_train, y_train), (X_test, y_test) = cifar10.load_data()
    if cfg.randomlbls:
        y_train = np.random.randint(0, len(np.unique(y_train)), y_train.shape)
    obj_classes = ['airplane', 'automobile', 'bird', 'cat',
                   'deer', 'dog', 'frog', 'horse', 'ship', 'truck']
    for (X_data, y_data, bp) in [(X_train, y_train, cfg.trainfolder), (X_test, y_test, cfg.testfolder)]:
        for c in obj_classes:
            os.makedirs(os.path.join(bp, c), exist_ok=True)
        for i, (im, lbl) in tqdm.tqdm(enumerate(zip(X_data, y_data)), desc='Making data folder', total=len(y_data)):
            pn = os.path.join(bp, obj_classes[int(lbl)], "%d.png" % i)
            if not os.path.exists(pn):
                scipy.misc.imsave(pn, scipy.misc.imresize(
                    im, cfg.imsize, interp='bicubic'))
# makedata(cfg.basepath)  # Comment out this line to use your own data
#%% Dataset loader


class DataSet:

    def __init__(self):
        self.columns = ['Type', 'Path', 'Class', 'Fname',
                        'xTrain', 'xCorrect', 'xWrong', 'Mean', 'Var']
        self.configfile = os.path.join(cfg.basepath, 'dataset.csv')
        self.data = pd.DataFrame(columns=self.columns)
        if os.path.exists(self.configfile):
            self.data = pd.read_csv(self.configfile)

    def scan(self):
        to_insert = []
        for t, d in [('Train', cfg.trainfolder), ('Test', cfg.testfolder)]:
            for root, dir, files in tqdm.tqdm(os.walk(d), mininterval=3, desc='Scanning data folder...'):
                for f in files:
                    cls = os.path.split(root)[-1]
                    path = os.path.join(root, f)
                    if path in self.data['Path']:
                        continue  # Ignore files that we've already seen
                    if f[0] == '.':
                        continue               # Ignore hidden files
                    if img_extension not in f.lower():
                        continue
                    row = (t, path, cls, f, 0, 0, 0, np.nan, np.nan)
                    to_insert.append(row)
        newdata = pd.DataFrame(data=to_insert, columns=self.columns)
        self.data = pd.concat([self.data, newdata])
        self.data = self.data.drop_duplicates(['Path'])
        self.data.to_csv(self.configfile, index=False)
        return self.data

dataset = DataSet().scan()
#%% Load train data


def load_data(basepath, samples_per_class=3):
    """Loads image data using folder names as class names
       Beware: make sure all images are the same size, or resize them manually"""
    import scipy.misc
    import skimage.color
    obj_classes = sorted([x for x in os.listdir(basepath) if x[0] != '.'])
    xdata, ydata = [], []
    for root, dirs, files in tqdm.tqdm(os.walk(basepath), mininterval=3, desc='Loading batch data', total=len(obj_classes)):
        random.shuffle(dirs)
        for i, f in enumerate(random.sample(files, min(len(files), samples_per_class))):
            if img_extension not in f.lower():
                continue
            try:
                im = scipy.misc.imread(os.path.join(root, f))
                im = scipy.misc.imresize(im, cfg.imsize, interp='bicubic')
                if cfg.hsv:
                    im = skimage.color.rgb2hsv(im)
            except OSError:
                print("Warning: corrupt file %s" % os.path.join(root, f))
                continue
            xdata.append(im)
            cls = os.path.split(root)[-1]
            clsid = obj_classes.index(cls)
            ydata.append(clsid)
    print("Loaded %d samples" % len(xdata))
    shuffle_ind = list(range(len(xdata)))
    random.shuffle(shuffle_ind)
    xdata = np.array(xdata, dtype='float32')
    xdata -= xdata.min()
    xdata /= xdata.max()
    return xdata[shuffle_ind], np.array(ydata, dtype='float32')[shuffle_ind], obj_classes

# Load test data
from keras.utils import np_utils
X_test, y_test, obj_classes = load_data(
    cfg.testfolder, samples_per_class=test_samples_per_class)
class_to_idx = dict([(y, x) for (x, y) in enumerate(obj_classes)])
img_rows, img_cols, img_channels = X_test.shape[1:]
Y_test = np_utils.to_categorical(y_test, len(obj_classes))

#%% VGG net definition
# VGG net definition starts here. Change the vgglayers to set how many
# layers to transfer
from keras.models import Model
from keras.regularizers import l1_l2
from keras.layers import Flatten, Dense, Input, Convolution2D, MaxPooling2D, BatchNormalization

img_input = Input(shape=cfg.tsize)
if cfg.vgglayers == 0:
    x = img_input
if cfg.vgglayers >= 1:  # Block 1
    x = Convolution2D(64, (3, 3), activation='relu',
                      padding='same', name='block1_conv1')(img_input)
    x = Convolution2D(64, (3, 3), activation='relu',
                      padding='same', name='block1_conv2')(x)
    x = MaxPooling2D((2, 2), strides=(2, 2), name='block1_pool')(x)
    if cfg.batchnorm:
        x = BatchNormalization()(x)
if cfg.vgglayers >= 2:  # Block 2
    x = Convolution2D(128, (3, 3), activation='relu',
                      padding='same', name='block2_conv1')(x)
    x = Convolution2D(128, (3, 3), activation='relu',
                      padding='same', name='block2_conv2')(x)
    x = MaxPooling2D((2, 2), strides=(2, 2), name='block2_pool')(x)
    if cfg.batchnorm:
        x = BatchNormalization()(x)
if cfg.vgglayers >= 3:  # Block 3
    x = Convolution2D(256, (3, 3), activation='relu',
                      padding='same', name='block3_conv1')(x)
    x = Convolution2D(256, (3, 3), activation='relu',
                      padding='same', name='block3_conv2')(x)
    x = Convolution2D(256, (3, 3), activation='relu',
                      padding='same', name='block3_conv3')(x)
    x = MaxPooling2D((2, 2), strides=(2, 2), name='block3_pool')(x)
    if cfg.batchnorm:
        x = BatchNormalization()(x)
if cfg.vgglayers >= 4:  # Block 4
    x = Convolution2D(512, (3, 3), activation='relu',
                      padding='same', name='block4_conv1')(x)
    x = Convolution2D(512, (3, 3), activation='relu',
                      padding='same', name='block4_conv2')(x)
    x = Convolution2D(512, (3, 3), activation='relu',
                      padding='same', name='block4_conv3')(x)
    x = MaxPooling2D((2, 2), strides=(2, 2), name='block4_pool')(x)
    if cfg.batchnorm:
        x = BatchNormalization()(x)
if cfg.vgglayers >= 5:  # Block 5
    x = Convolution2D(512, (3, 3), activation='relu',
                      padding='same', name='block5_conv1')(x)
    x = Convolution2D(512, (3, 3), activation='relu',
                      padding='same', name='block5_conv2')(x)
    x = Convolution2D(512, (3, 3), activation='relu',
                      padding='same', name='block5_conv3')(x)
    x = MaxPooling2D((2, 2), strides=(2, 2), name='block5_pool')(x)
    if cfg.batchnorm:
        x = BatchNormalization()(x)

x = Flatten(name='flatten')(x)
for i in range(cfg.fclayers):
    x = Dense(cfg.fclayersize, activation='relu',
              kernel_regularizer=l1_l2(cfg.l1, cfg.l2))(x)
x = Dense(len(obj_classes), activation='softmax', name='predictions')(x)

inputs = img_input
model = Model(inputs, x, name='vgg16')
model.compile(loss='categorical_crossentropy',
              optimizer=optimizer, metrics=['accuracy'])
model.summary()
#%% Transfer weights
from keras.applications import vgg16
import keras.layers.convolutional
vgg16model = vgg16.VGG16(include_top=False)
modelconv = [l for l in model.layers if type(
    l) == keras.layers.convolutional.Conv2D]
vgg16conv = [l for l in vgg16model.layers if type(
    l) == keras.layers.convolutional.Conv2D]

for i, l in enumerate(modelconv):
    if i > cfg.xferlearning:
        continue  # Transfer only first n layers
    print('**** Transferring layer %d: %s from VGG ****' % (i, l))
    weights = vgg16conv[i].get_weights()
    modelconv[i].set_weights(weights)
    if cfg.freeze_conv:
        l.trainable = False
#%% Visualization code


def viz_losses(stats, epoch):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 6))
    epoch = len(stats)
    fig.suptitle("Training vgglayers=%d, fclayers=%d, fcsize=%d, epoch=%d" % (
        cfg.vgglayers, cfg.fclayers, cfg.fclayersize, epoch))
    ax1.plot(stats['Train loss'].values, label='Train loss', color='blue')
    ax1.plot(stats['Test loss'].values, label='Test loss', color='green')
    ax1.set_yscale('log')
    ax2.plot(stats['Accuracy'].values, label='Test accuracies', color='red')
    ax2.plot(stats['Train accuracy'].values,
             label='Train accuracies', color='blue')
    ax2.axhline(1.0 / len(obj_classes), linestyle='dashed', color='gray')
    ax2.text(0, 1.0 / len(obj_classes), 'Chance')
    ax2.axhline(np.max(stats['Accuracy']), linestyle='dashed', color='red')
    ax2.text(0, np.max(stats['Accuracy']), 'Best')
    ax2.set_ylim([0, 1])
    ax2.set_title('Accuracy: %0.2f%%' % (100.0 * stats['Accuracy'].values[-1]))
    ax1.legend(), ax2.legend()
    plt.savefig(os.path.join(cfg.basepath, cfg.model_subdirectory, "loss", 'loss-epoch-' + str(epoch).rjust(5, "0") + '.png'))
    plt.show()
    plt.close()
#%% Explanations
import skimage.exposure
import skimage.filters
from skimage.color import gray2rgb
from keras import backend as K


def hide_axes(ax): ax.set_xticks([]), ax.set_yticks([])


class Heatmap:

    def __init__(self, model, obj_classes):
        self.obj_classes = obj_classes
        self.nclasses = len(obj_classes)
        self.model = model

    def make_masks(self, im, n=8, maskval=0.1):
        masks = []
        xwidth, ywidth = int(
            np.ceil(im.shape[0] / n)), int(np.ceil(im.shape[1] / n))
        for i in range(n):
            for j in range(n):
                mask = np.ones(im.shape[:2])
                mask[(i * xwidth):((i + 1) * xwidth),
                     (j * ywidth):((j + 1) * ywidth)] = maskval
                # Change this for local mask smoothing
                mask = skimage.filters.gaussian(mask, 1)
                masks.append(mask)
        return np.array(masks)

    def explain_prediction_heatmap(self, im, actual, epoch):
        import skimage.color

        def hsv(im): return skimage.color.hsv2rgb(im) if cfg.hsv else im
        plt.imshow(hsv(im)), plt.xticks([]), plt.yticks(
            []), plt.title('Full image'), plt.show(), plt.close()
        masks = np.concatenate([self.make_masks(im, n=i)
                                for i in (9, 7, 5, 3, 2)])
        masknorm = masks.sum(axis=0)
        heatmaps = np.zeros((self.nclasses,) + im.shape[:2])
        for m in masks:
            prediction = self.model.predict(
                np.expand_dims(im * gray2rgb(m), 0))
            for c in range(self.nclasses):
                heatmaps[c] += (prediction[0][c] * m)
        for h in heatmaps:
            h = h / masknorm
        fig, axes = plt.subplots(2, self.nclasses + 1, figsize=(20, 5))
        axes[0, 0].imshow(hsv(im)), axes[1, 0].imshow(im)
        axes[0, 0].set_title(actual)
        axes[1, 0].set_title('HSV' if cfg.hsv else 'RGB')
        hide_axes(axes[0, 0]), hide_axes(axes[1, 0])
        predictions = np.sum(heatmaps, axis=(1, 2,))
        predictions /= predictions.max()
        for n, i in enumerate(np.argsort(predictions)[::-1][:self.nclasses]):
            h = ((255 * heatmaps[i]) / heatmaps[i].max()).astype('uint16')
            h = skimage.exposure.equalize_adapthist(h)
            # Change this for global mask smoothing
            h = skimage.filters.gaussian(h, 1)
            axes[0, n + 1].imshow(gray2rgb(h))
            axes[1, n + 1].imshow(gray2rgb(h) * hsv(im)
                                  * (0.5 + 0.5 * predictions[i]))
            hide_axes(axes[0, n + 1]), hide_axes(axes[1, n + 1])
            axes[0, n + 1].set_title(self.obj_classes[i] +
                                     ': %0.1f%%' % (100 * predictions[i] / predictions.sum()))
        fig.tight_layout()
        plt.savefig(os.path.join(cfg.basepath, cfg.model_subdirectory, "heatmaps", "heatmap-epoch-" + str(epoch) + ".png"))
        plt.show()
        plt.close()
        return heatmaps


class Viz_filters:

    def __init__(self, model, img_input, img_rows, img_cols):
        self.layer_dict = dict([(layer.name, layer) for layer in model.layers])
        self.img_input = img_input
        self.img_rows = img_rows
        self.img_cols = img_cols

    def deprocess_image(self, x):
        x -= x.mean()
        x /= (x.std() + 1e-5)
        x = x * 0.1 + 0.5
        x = np.clip(x, 0, 1) * 255
        x = np.clip(x, 0, 255).astype('uint8')
        return x

    def viz_filter_max(self, layer_name, filter_index=0, max_steps=9999, timeout=3):
        layer_output = self.layer_dict[layer_name].output
        loss = K.mean(layer_output[:, :, :, filter_index])

        grads = K.gradients(loss, self.img_input)[0]
        grads /= (K.sqrt(K.mean(K.square(grads))) + 1e-5)
        iterate = K.function([self.img_input], [loss, grads])
        step = 1e-0
        input_img_data = np.random.random((1, self.img_rows, self.img_cols, 3))
        input_img_data = (input_img_data - 0.5) * 20 + 128

        tm = time.time()
        print("\nVisualizing filters.")
        for i in tqdm.tqdm(range(max_steps), desc='Filter visualization', mininterval=3):
            loss_value, grads_value = iterate([input_img_data])
            input_img_data += grads_value * step
            if time.time() - tm > timeout:
                plt.text(0.1, 0.1, "Filter viz timeout", color='red')
                break
        img = input_img_data[0]
        img = self.deprocess_image(img)
        fig = plt.imshow(img)
        hide_axes(fig.axes)
        return layer_output

    def viz_filters(self, nbfilters=3):
        print("Visualizing filters (CTRL-C to cancel)")
        try:
            for layer_name in sorted(self.layer_dict.keys()):
                if not hasattr(self.layer_dict[layer_name], 'filters'):
                    continue
                nfilters = self.layer_dict[layer_name].filters
                print("Layer", layer_name, "has", nfilters, "filters")
                plt.subplots(1, nbfilters)
                for j in range(nbfilters):
                    plt.subplot(1, nbfilters, j + 1)
                    self.viz_filter_max(layer_name, random.randint(
                        0, nfilters - 1), timeout=cfg.vizfilt_timeout)
                plt.savefig(os.path.join(
                    cfg.basepath, cfg.model_subdirectory, 'filters', 'filters-' + str(epoch).rjust(5, "0") + ".png"))
                plt.show()
                plt.close()
        except KeyboardInterrupt:
            return


class Explainer:

    def __init__(self, model, obj_classes, class_to_idx):
        self.model = model
        self.obj_classes = obj_classes
        self.class_to_idx = class_to_idx
        self.show_conv_filters = show_conv_filters
        self.show_heatmap = show_heatmap
        if self.show_heatmap:
            heatmap_path = os.path.join(cfg.basepath, cfg.model_subdirectory, "heatmaps")
            os.makedirs(heatmap_path, exist_ok=True)

    def explain(self, im, cls, epoch):
        heatmap = Heatmap(self.model, self.obj_classes)
        if self.show_heatmap:
            heatmap.explain_prediction_heatmap(im, self.obj_classes[cls], epoch)


explainer = Explainer(model, obj_classes, class_to_idx)


#%%
def test_prediction(im=None, y=None, epoch=0):
    t_img = random.randint(0, len(X_train) - 1)
    if im is None:
        im, y = X_train[t_img], Y_train[t_img]
    pred = model.predict(np.expand_dims(im, 0))
    cls = np.argmax(y)
    explainer.explain(im, cls, epoch)
    print("Actual: %s(%d)" % (obj_classes[cls], cls))
    for cls in list(reversed(np.argsort(pred)[0]))[:5]:
        conf = float(pred[0, cls]) / pred.sum()
        print("    predicted: %010s(%d), confidence=%0.2f [%-10s]" % (
            obj_classes[cls], cls, conf, "*" * int(10 * conf)))
    return pred


#%% Training code
datagen.fit(X_test)
if cfg.saveloadmodel and os.path.exists(cfg.modelid):
    print("**** Loading existing model: %s ****" % cfg.modelid)
    model.load_weights(cfg.modelid)


#%%
import gc
vizfilt = Viz_filters(model, img_input, img_rows, img_cols)
trainstats = pd.DataFrame(
    columns=('Train loss', 'Test loss', 'Accuracy', 'Train accuracy'))
if os.path.exists(cfg.trainstats):
    trainstats = pd.read_csv(cfg.trainstats, dtype='float32')

X_train, y_train, obj_classes = load_data(cfg.trainfolder, cfg.spercls)
Y_train = np_utils.to_categorical(y_train, len(obj_classes))
for e in range(cfg.nb_epoch):
    print('Training.ß.. epoch=%d/%d' % (e, cfg.nb_epoch))
    loss = model.fit_generator(datagen.flow(X_train, Y_train, shuffle=True,
                                            batch_size=cfg.batch_size),
                               steps_per_epoch=1,
                               epochs=1,
                               validation_data=(X_test, Y_test),
                               verbose=0)
    print("Accuracy:", loss.history['val_acc'][0] * 100)
    tloss = model.evaluate(X_train, Y_train)
    if cfg.saveloadmodel and e % 50 == 0:
        model.save_weights(cfg.modelid, overwrite=True)
    trainstats.loc[len(trainstats)] = (loss.history['loss'][0], loss.history[
        'val_loss'][0], loss.history['val_acc'][0], tloss[1])
    if e % 10 == 0:
        trainstats.to_csv(cfg.trainstats, index=False)
        viz_losses(trainstats, e)
        t_ind = random.randint(0, len(X_test) - 1)
        test_prediction(X_test[t_ind], Y_test[t_ind], epoch=e)
    if e % 30 == 29 and cfg.vizfilt_timeout > 0:
        vizfilt.viz_filters()
    check_memusage()
    gc.collect()
