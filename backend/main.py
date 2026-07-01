"""Backend compatibility entrypoint.

TODO: Delegate to the app package while the migration is in progress.
"""

from app.main import main


if __name__ == "__main__":
	print(main())

