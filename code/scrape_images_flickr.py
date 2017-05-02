import flickrapi
import os
import lxml.etree as etree
import urllib

"""
Parameters

directory: main directory where images will be stored
styles_dict: dict with each key as style name and value is a list of search terms
n_per_class: number of images to download per style
"""
directory = "../data/flickr"
styles_dict = {'cubism': ['cubist painting', 'cubism painting'],
               'pop-art': ['pop art painting'],
               'hyperrealism': ['hyperrealistic painting', 'hyperrealism painting'],
               'impressionism': ['impressionist painting', 'impressionism painting'],
               'abstract-expressionism': ['abstract expressionist painting', 'abstract expressionism painting']}
n_per_class = 20000


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

        for i, url in enumerate(url_list):
            # Grab file extension
            ext = url[-4:]
            filename = os.path.join(dirpath, (classname + "-%05d" + ext) % i)

            # Some images are displayed without file extension
            if filename[-4:] not in ['.jpg', '.png', 'jpeg']:
                filename += '.jpg'

            try:
                urllib.request.urlretrieve(url, filename=filename)
            except Exception:
                print("url", url, "\nfilename", filename)
                print("Skipping image ", url_list.index(url))

            print(url_list.index(url), " of ", len(url_list), "downloaded")

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
    scraper.api_key = "d5eda11e632ed843b734e3523e68dd17"
    scraper.api_secret = "8066a5cfc85455b3"
    scraper.data_directory = directory

    for style in styles_dict.keys():
        terms = styles_dict[style]
        for term in terms:
            scraper.download_images(searchterm=term, classname=style, n=round(n_per_class / len(terms)))
