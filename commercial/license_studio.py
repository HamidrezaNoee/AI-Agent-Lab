"""Compatibility entrypoint only.

The earlier experimental LIMAK-AIA1 token here was NOT compatible with the
signed tenant license accepted by the active commercial GodAdmin API.
All keygen, issue and inspect operations must use the ONE authoritative
commercial.licensing.studio / commercial.licensing.codec implementation.
Never import a private signing key into a customer API/server.
"""


def main():
    from .licensing.studio import main as trusted_studio_main
    return trusted_studio_main()


if __name__ == "__main__":
    main()
