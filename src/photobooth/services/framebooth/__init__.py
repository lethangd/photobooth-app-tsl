"""Self-service kiosk ("Framebooth") domain logic.

The HTTP layer lives in ``photobooth.routers.api.framebooth`` and only wires
requests to the helpers in this package:

- ``models``       - ``FrameSlot`` / ``FrameTemplate`` value objects
- ``templates``    - auto-discovery of frame templates from ``photobooth/frame/*``
- ``filters``      - the selectable color filters (config driven) + PIL implementation
- ``renderer``     - compositing captures into a framed collage image
- ``timelapse``    - server-side timelapse video fallback (OpenCV)
- ``session_store``- short-lived storage for captures/timelapses of the current guest
"""
