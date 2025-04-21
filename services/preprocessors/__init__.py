# Import service modules to ensure services are registered when this package is imported.
from . import moving_average
from . import merge_1d

# Optionally, define __all__ if you want to control what 'from services.preprocessors import *' imports
# __all__ = ['moving_average', 'merge_1d'] # Or just leave it empty/undefined 