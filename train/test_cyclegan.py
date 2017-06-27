import os
import shutil
import subprocess
import time
import pylab
import imageio
import numpy as np
from tqdm import tqdm
from skimage.io import imread, imsave


def create_options(model, epoch):
    opts_test = {
        "loadSize": 512,
        "fineSize": 512,
        "how_many": 'all',
        "phase": 'test',
        "name": model,
        "checkpoints_dir": './checkpoints',
        "results_dir": '.temp_output',
        "which_epoch": str(epoch),
        "which_direction": 'AtoB',
        "resize_or_crop": '"scale_width"',
    }
    return opts_test


def create_bash_cmd_test(opts_test):
    """constructs bash command to run CycleGAN with the given settings"""
    cmd = []
    cmd.append("DATA_ROOT=.temp_input")
    for opt in opts_test.keys():
        cmd.append(opt + "=" + str(opts_test[opt]))
    cmd += ['th', 'test.lua']
    return(" ".join(cmd))


def check_correct_directory():
    """check if the script is being run from CycleGAN"""
    fpath = os.path.realpath(__file__)
    dirname = os.path.dirname(fpath).split('/')[-1]
    if not dirname == "CycleGAN":
        raise ValueError("Script should be run from CycleGAN base directory.")


def prep_directories():
    """ensures clean temporary directories for CycleGAN"""
    for dir_ in ['.temp_input', '.temp_output']:
        if os.path.exists(dir_):
            shutil.rmtree(dir_)
    for dir_ in ['testA', 'testB']:
        os.makedirs(os.path.join('.temp_input', dir_))
    os.makedirs(os.path.join('.temp_output'))


def grab_epochs(model):
    """
    given a model name or a folder path,
    returns an array of available epochs
    """
    if not os.path.isdir(model):
        model = os.path.join('checkpoints', model)
    assert os.path.isdir(model), model + " not a valid model"

    epochs = []
    for file in os.listdir(model):
        if file.split('.')[-1] == "t7":
            epochs.append(file.split('_')[0])
    epochs = [e for e in epochs if not e == 'latest']

    return list(set(epochs))


def test(img, opts):
    """
    performs a test inference on img, saves to a temp directory
    returns the stylized image
    """
    prep_directories()
    for dir_ in ['testA', 'testB']:
        imsave(os.path.join('.temp_input', dir_, 'img.png'), img)

    # run the bash command for test phase of CycleGAN
    cmd = create_bash_cmd_test(opts)

    start = time.time()
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    process.wait()
    print("Stylizing complete. Time elapsed:", time.time() - start)

    # read image back into python
    path = os.path.join('.temp_output', opts['name'], str(opts['which_epoch']) + "_test", "images", "fake_B", "img.png")
    stylized_img = imread(path)
    return stylized_img


def stylize_image_all_epochs(img_path, output_dir, model):
    """
    processes an image with a model at all available epochs
    """
    imname = os.path.split(img_path)[1].split('.')[0]
    os.makedirs(output_dir, exist_ok=True)

    img = imread(img_path)
    available_epochs = grab_epochs(model)

    for epoch in tqdm(available_epochs):
        opts = create_options(model, epoch)
        stylized_img = test(img, opts)
        imsave(os.path.join(output_dir, imname + "-" + model + "-epoch-" + str(epoch)) + ".png", stylized_img)


def stylize_video(vid_path, out_path, model, epoch):
    """
    stylizes all frames of a video
    """
    video = imageio.get_reader(vid_path, 'mpeg')
    writer = imageio.get_writer(out_path, fps=30)
    opts = create_options(model, epoch)

    # TODO: don't hardcode 30fps downsampling
    for i, frame in enumerate(video):
        if i % 2 == 0:
            frame = test(np.array(frame), opts)
            writer.append_data(frame)
        if i % 10 == 0:
            print(i, "of", len(video), "frames done.")
        if i == len(video) - 10:  # TAKE THIS OUT AFTER DONE TESTING
            break
    writer.close()


def repeat_stylization(img_path, out_dir, n_iter, model, epoch):
    """
    Repeatedly applies a style to an image
    """
    fname = os.path.splitext(img_path)[0].split("/")[-1]
    img = imread(img_path)
    os.makedirs(out_dir, exist_ok=True)
    opts = create_options(model, epoch)

    for i in range(n_iter):
        img = test(img, opts)
        imsave(os.path.join(out_dir, fname + "-" + model + "-" + str(epoch) + "-iter" + i))


def stylize_dir_hacky(input_dir, output_dir):
    """
	this is horrible and last minute
    temporary function to perform stylization
    images: applies 3 available styles at 5 different epochs
    the bean - pop art at all epochs
    northwestern - cubism at all epochs
    video: applies 3 styles to each video
    """
    models = ['cubism_v2', 'impressionism', 'pop_art']
    epochs_img = [50, 100, 150, 200]
    files = os.listdir(input_dir)
    files = [f for f in files if not f[0] == "."]
    os.makedirs(output_dir)

    for file in files:
        filename = file.split(".")[0]
        output_subdir = os.path.join(output_dir, filename + "-stylized")
        os.makedirs(output_subdir, exist_ok=True)

        print("Stylizing", file, "\nSaving to", output_subdir)

        # Videos
        if ".mp4" in file:
            for model in models:
                print("Applying", model, "to", file, ", saving to")
                stylize_video(vid_path=os.path.join(input_dir, file),
                              out_path=os.path.join(output_subdir, file + '-' + model + '.mp4'),
                              model=model,
                              epoch=200)

        # Photos
        else:

            # Images, all epochs, all models
            if file in ['northwestern.jpeg', 'the_bean.jpeg']:
                output_subdir_all_epochs = os.path.join(output_dir, file.split(".")[0] + "-all-epochs")
                os.makedirs(output_subdir_all_epochs, exist_ok=True)
                for model in models:
                    print("Applying", model, "to", file, "all epochs", "\nSaving to", output_subdir_all_epochs)
                    # try:
                    stylize_image_all_epochs(img_path=os.path.join(input_dir, file),
                                             output_dir=output_subdir_all_epochs,
                                             model=model)
                    # except:
                    #     pass

            # Images, only certain styles
            for model in models:
                for epoch in epochs_img:
                    try:
                        img = imread(os.path.join(input_dir, file))
                        opts = create_options(model, epoch)
                        stylized_img = test(img, opts)
                        imsave(os.path.join(output_subdir, filename + "-" + model + "-epoch-" + epoch + ".png"), stylized_img)
                    except:
                        pass


def stylize_image_all_styles(img_path, models):
    pass


if __name__ == "__main__":
    stylize_dir_hacky("input_5-28-17", "output_5-28-17")
