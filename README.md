# Realtime Logs
To monitor realtime logs while running the capability you can use logger from **worker** object inside **call** method. 
## Logging with levels
Example: 
```
worker.editor_logging_handler.info("Info logging...")
worker.editor_logging_handler.warning("Warning logging...")
worker.editor_logging_handler.debug("Warning logging...")
worker.editor_logging_handler.error("Warning logging...")
worker.editor_logging_handler.critical("Warning logging...")
```
