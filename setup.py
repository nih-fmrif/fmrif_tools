""" FMRIF Tools setup script """


def main():

    from setuptools import setup, find_packages
    from __about__ import (
        __version__,
        __author__,
        __email__,
        __copyright__,
        __license__,
        __description__,
        __longdesc__,
        __url__,
        __download__,
        PACKAGE_NAME,
        CLASSIFIERS,
        REQUIRES,
    )

    pkg_data = {
        'common_utils': ['data/config.json']
    }

    version = __version__

    setup(
        name=PACKAGE_NAME,
        version=version,
        description=__description__,
        long_description=__longdesc__,
        author=__author__,
        author_email=__email__,
        copyright=__copyright__,
        license=__license__,
        maintainer_email=__email__,
        classifiers=CLASSIFIERS,
        install_requires=REQUIRES,
        url=__url__,
        download_url=__download__,
        entry_points={
            'console_scripts': [
                'oxy2bids=oxy2bids.gen_bids:main',
                'process_biopac=biounpacker.biopac_organize:main',
                'dcmexplorer=dcmexplorer.explorer:main',
                'bidsmapper=bidsmapper.mapper:main'
            ]
        },
        packages=find_packages(),
        package_data=pkg_data,
        zip_safe=False,
    )


if __name__ == '__main__':
    main()
