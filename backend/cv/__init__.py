"""
HelioOps CV layer — CME detection from coronagraph imagery.

Three stages, run in order:
  data_ingestion            → raw inputs (FITS frames, DONKI, GOES XRS, DSCOVR L1)
  image_threshold_algorithm → preprocess frames, run the threshold detector
  storm_event_generator     → fuse everything into a StormEvent
"""
