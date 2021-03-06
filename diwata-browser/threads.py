import json
import requests
import os

from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QIcon, QImage, QPixmap

from .settings import URL
from .models import Item
from .models import Collection

current_dir = os.path.dirname(os.path.abspath(__file__))
no_prev_path = os.path.join(current_dir, 'no_preview_available.jpg')


class LoadItem(QThread):
    debugger_signal = pyqtSignal(str)
    item_info = pyqtSignal(Item)
    thumbnail_signal = pyqtSignal(QPixmap)
    error_signal = pyqtSignal()
    footprint_signal = pyqtSignal(Item)

    def __init__(self, download_path, item_id):
        QThread.__init__(self)

        self.download_path = download_path
        self.item_id = item_id

    def run(self):
        url = "{url}/stac_management/stac/collections/diwata-2-smi/items/{item_id}".format(
            url=URL,
            item_id=self.item_id)

        try:
            response = requests.get(url)
        except Exception:
            self.error_signal.emit()
            return

        if response.status_code != 200:
            self.error_signal.emit()
            return

        item = Item(response.json())
        self.item_info.emit(item)
        self.footprint_signal.emit(item)
        thumbnail = self.get_thumbnail(item)

        if thumbnail is None:
            pixmap = QPixmap(no_prev_path)
            self.thumbnail_signal.emit(pixmap)
            return

        pixmap = QPixmap()
        pixmap.loadFromData(requests.get(thumbnail).content)

        self.thumbnail_signal.emit(pixmap)
        return

    def get_thumbnail(self, item):
        for asset in item.get_assets():
            if asset.key == 'thumbnail':
                thumbnail = asset.href
                return thumbnail
        return None


class LoadCollection(QThread):
    listed_items_signal = pyqtSignal(list)
    error_signal = pyqtSignal()

    def __init__(self, start_time=None, end_time=None, bbox=None):
        QThread.__init__(self)

        self.start_time = start_time
        self.end_time = end_time
        self.bbox = bbox

    def run(self):
        headers = {'content-type': 'application/json'}
        payload = {'datetime': '{}/{}'.format(
            self.start_time, 
            self.end_time)
        }
        if self.bbox is not None:
            payload['bbox'] = self.bbox

        url = "{url}/stac_management/stac/search".format(url=URL)
        
        try:
            response = requests.post(url, json=payload, headers=headers)
        except Exception:
            self.error_signal.emit()
            return

        if response.status_code != 200:
            self.error_signal.emit()
            return

        features = response.json()['features']

        items = [item.get('id') for item in features]
        self.listed_items_signal.emit(items)
        return


class LoadRaster(QThread):
    error_signal = pyqtSignal()
    raster_downloaded = pyqtSignal(str, str)

    def __init__(self, download_path=None, item_id=None):
        QThread.__init__(self)

        self.download_path = download_path
        self.item_id = item_id
        self.url = self.item_id.assets['cloud_optimized_geotiff']['href']

    def run(self):
        response = requests.get(self.url, allow_redirects=True)
        basename = os.path.basename(self.url)
        save_to = os.path.join(self.download_path, basename)

        with open(save_to, 'wb') as f:
            f.write(response.content)

        self.raster_downloaded.emit(save_to, basename)

