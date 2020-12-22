# DO NOT EDIT!!! built with `python _building/build_setup.py`
import setuptools
setuptools.setup(
    name="md2zhihu",
    packages=["md2zhihu",
              "md2zhihu.mistune",
              "md2zhihu.md2zhihu",
              "md2zhihu.mistune.plugins"],
    version="0.1.6",
    license='MIT',
    description='convert markdown to zhihu compatible format.',
    long_description='# md2zhihu\nConvert markdown to zhihu compatible format\n',
    long_description_content_type="text/markdown",
    author='Zhang Yanpo',
    author_email='drdr.xp@gmail.com',
    url='https://github.com/pykit3/md2zhihu',
    keywords=['python', 'markdown', 'zhihu'],
    python_requires='>=3.0',

    entry_points = {
        'console_scripts': [
            'md2zhihu = md2zhihu:main',
        ],
    },

    install_requires=['PyYAML~=5.3.1', 'k3proc', 'k3down2', 'k3ut~=0.1.7'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
    ] + ['Programming Language :: Python :: 3'],
)
