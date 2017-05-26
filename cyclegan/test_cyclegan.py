import os
import shutil
import subprocess
from skimage.io import imread, imsave


def create_options(name, epoch):
    opts_test = {
        "loadSize": 512,
        "fineSize": 512,
        "how_many": 'all',
        "phase": 'test',
        "name": name,
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


def grab_available_epochs(model):
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
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    process.wait()

    # read image back into python
    path = os.path.join('.temp_output', name, str(opts['which_epoch']) + "_test", "images", "fake_B", "img.png")
    stylized_img = imread(path)
    return stylized_img


if __name__ == "__main__":
    check_correct_directory()
    prep_directories()
    im = imread("input/testA/the_bean.jpeg")
    
    print('styleizing')
    styleized_im = test(im)
    imsave("test_output.png", styleized_im)
    pass
