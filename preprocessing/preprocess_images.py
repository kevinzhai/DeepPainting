import os
from skimage import io, transform
import tqdm

# PARAMETERS
IMAGE_DIRECTORY = "../data/flickr"
RESOLUTION = 32


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


def process_all_imgs(img_dir, target_dir):
    """
    processes all images in img_dir, applying square crop and resize
    saves processed images to target_dir
    """
    os.makedirs(target_dir, exist_ok=True)
    img_list = os.listdir(img_dir)

    print("Processing images from:", img_dir, "\nSaving images to:", target_dir)
    for img_fname in tqdm.tqdm(img_list):

        img = io.imread(os.path.join(img_dir, img_fname))
        if is_color(img):
            img = square_crop(img)
            img = correct_resolution(img, RESOLUTION)  # change to 224 resolution
            io.imsave(os.path.join(target_dir, img_fname), (img * 256).astype("uint8"))


if __name__ == "__main__":
    image_dirs = next(os.walk(IMAGE_DIRECTORY))[1]
    for dir_ in image_dirs:
        process_all_imgs(os.path.join(IMAGE_DIRECTORY, dir_), os.path.join(IMAGE_DIRECTORY, dir_ + "-processed"))
