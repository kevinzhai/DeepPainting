import flickrapi
import os
import lxml.etree as etree
import urllib
from tqdm import tqdm

"""
Parameters

directory: main directory where images will be stored
styles_dict: dict with each key as style name and value is a list of search terms
n_per_class: number of images to download per style
"""
directory = "../data/flickr"
styles_dict = {'sumie': ['chinese painting landscape']}
n_per_class = 800


class FlickrScraper:
    def __init__(self):
        self.api_key = None
        self.api_secret = None
        self.data_directory = None

    def download_images(self, searchterm, classname, n):
        '''
        Download all images from 'url_list' to directory 'directory'
        directory: desired folder name, such as "squirrelpic"
        '''
        assert self.api_key is not None, "Please provide a Flickr api key."
        assert self.api_secret is not None, "Please provide a Flickr api secret."
        assert self.data_directory is not None, "Please set a root data directory."

        dirpath = os.path.join(os.getcwd(), self.data_directory, classname)
        os.makedirs(dirpath, exist_ok=True)

        print("Requesting", n, "images with search term:", searchterm, "\n"
              "Results will be saved in:", dirpath, "\n")

        url_list = self.get_flickr_url_list(searchterm, n)
        initial_file_count = len(os.listdir(dirpath))

        for i, url in enumerate(tqdm(url_list)):
            # Grab file extension
            ext = url[-4:]
            filename = os.path.join(dirpath, (classname + "-%05d" + ext) % (initial_file_count + i))

            # Some images are displayed without file extension
            if filename[-4:] not in ['.jpg', '.png', 'jpeg']:
                filename += '.jpg'

            try:
                urllib.request.urlretrieve(url, filename=filename)
            except Exception:
                print("url", url, "\nfilename", filename)
                print("Skipping image ", url_list.index(url))

    def get_flickr_url(self, node):
        '''
        returns the static image url given by a child node of the XML elementtree
        '''
        start = node.index("https://")
        end = node.index('" height_')
        return node[start:end]

    def get_flickr_url_list(self, searchterm, n):
        '''
        Returns list of urls with searching for searchterm
        '''
        flickr = flickrapi.FlickrAPI(self.api_key, self.api_secret)

        # Generate URL list
        urls = []
        retrieved = 0
        page = 0

        while retrieved < n:
            fsearch = flickr.photos_search(text=searchterm, page=page, per_page=500, extras=["url_m"], sort="relevance")
            page += 1

            # Iterate through each child node of the xmltree
            for i in range(0, 499):
                try:
                    # Must check for url as some are private
                    metadata = str(etree.tostring(fsearch[0][i]))
                    if 'url' in metadata:
                        urls.append(self.get_flickr_url(metadata))
                        retrieved += 1
                except Exception:
                    pass

                if retrieved % 100 == 0:
                    print(retrieved, 'urls retrieved')

                if retrieved >= n:
                    break

        return urls


if __name__ == "__main__":
    scraper = FlickrScraper()
    scraper.data_directory = directory

    for style in styles_dict.keys():
        terms = styles_dict[style]
        for term in terms:
            scraper.download_images(searchterm=term, classname=style, n=round(n_per_class / len(terms)))
