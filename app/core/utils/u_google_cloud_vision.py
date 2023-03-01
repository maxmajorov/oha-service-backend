from google.cloud import vision


def detect_web_uri(url):
    """Detects web annotations in the file located in Google Cloud Storage."""
    client = vision.ImageAnnotatorClient()
    response = client.annotate_image({
        'image': {'source': {'image_uri': url}},
        'features': [
            {
                'type': vision.enums.Feature.Type.WEB_DETECTION,
            }
        ],
        # "imageContext": {'webDetectionParams': {'includeGeoResults': True}},
    })
    web_detection = response.web_detection
    return web_detection
