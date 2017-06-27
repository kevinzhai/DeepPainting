import os
import tqdm
from random import shuffle
from skimage import io, transform

# PARAMETERS
IMAGE_DIRECTORY = "../data/flickr/"
RESOLUTION = 64


def is_color(img):
    """
    returns True if the image has 3 channels, signifying RGB
    """
    return len(img.shape) == 3


def square_crop(img):
    """
    crops an image into a square
    """
    (h, w, d) = img.shape
    h_center = h / 2
    w_center = w / 2

    if h < w:
        coords = (int(w_center - h / 2), int(w_center + h / 2))
        img = img[:, coords[0]:coords[1], :]
    elif h >= w:
        coords = (int(h_center - w / 2), int(h_center + w / 2))
        img = img[coords[0]:coords[1], :, :]

    assert img.shape[0] == img.shape[1], "Image is not a square."
    return img


def correct_resolution(img, res):
    """
    corrects resolution
    """
    return transform.resize(img, (res, res, 3))


def process_all_imgs(img_dir, target_dir, rename_imgs=False, shuffle_imgs=False):
    """
    processes all images in img_dir, applying square crop and resize
    saves processed images to target_dir
    """
    os.makedirs(target_dir, exist_ok=True)
    img_list = os.listdir(img_dir)
    if shuffle_imgs:
        img_list = shuffle(img_list)

    print("Processing images from:", img_dir, "\nSaving images to:", target_dir)
    for i, img_fname in tqdm.tqdm(enumerate(img_list)):
        print(img_fname)
        try:
            img = io.imread(os.path.join(img_dir, img_fname))
            if rename_imgs:
                img_fname = str(i).rjust(5, "0") + ".jpg"
            if is_color(img):
                img = square_crop(img)
                img = correct_resolution(img, RESOLUTION)  # change to 224 resolution
                io.imsave(os.path.join(target_dir, img_fname), (img * 256).astype("uint8"))
        except OSError:
            continue


if __name__ == "__main__":
    process_all_imgs("../cyclegan/results/cubism_v2_animation",
                     "../cyclegan/results/cubism_v2_animation_processed_64",
                     rename_imgs=False)
