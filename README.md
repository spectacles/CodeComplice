CodeComplice
=================

This Project started as a fork of the [SublimeCodeIntel](https://github.com/SublimeCodeIntel/SublimeCodeIntel) plugin.
I invested months of work to improve and refine the plugin and I intend to keep on doing so!
If you're coming from the original SublimeCodeIntel, take a **close** look at the ``Configuring`` section below!

---------------------------------------

Based on the open-source Code intelligence from [Open Komodo Editor](http://www.openkomodo.com/).

Supported languages for Code Intelligence (CIX, CodeIntel2):

    Go
    Python
    Python3
    Django
    PHP
    Perl
    Ruby
    JavaScript (Node.js basics)
    CSS, SCSS, Sass

other languages ported from Komodo but not revised:

    HTML, HTML5, Mason, RHTML, Smarty, Tcl, TemplateToolkit, Twig, XBL, XML, XSLT, XUL

Provides the following features:

* Jump to Symbol Definition - Jump to the file and line of the definition of a symbol.
* Imports autocomplete - Shows autocomplete with the available modules/symbols in real time.
* Function Call tooltips - Displays information in the status bar about the working function.

Plugin should work in all three platforms (MacOS X, Windows and Linux).


Installing
----------

#### with [Sublime Package Control](http://wbond.net/sublime_packages/package_control)

 1. Open command pallet (default: `ctrl+shift+p`)
 2. Type `package control install` and select command `Package Control: Install Package`
 3. Type `complice` and select "CodeComplice"

**Without Git:** Download the latest source from [GitHub](http://github.com/spectacles/CodeComplice) and copy the whole directory into the Packages directory.

**With Git:** Clone the repository in your Sublime Text Packages directory, located somewhere in user's "Home" directory::

    git clone git://github.com/spectacles/CodeComplice.git


The "Packages" packages directory is located differently in different platforms. To access the directory use:

##### OS X:

    Sublime Text -> Preferences -> Browse Packages...

##### Linux:

    Preferences -> Browse Packages...

##### Windows:

    Preferences -> Browse Packages...


Using
-----

* Start typing code as usual, autocomplete will pop up whenever it's available. CodeComplice will also allow you to jump around symbol definitions even across files with just a click ..and back.

  ***For Mac OS X:***
    * Jump to definition = ``Control+Click``
    * Jump to definition = ``Control+Command+Alt+Up``
    * Go back = ``Control+Command+Alt+Left``
    * Manual Code Intelligence = ``Control+Shift+space``

  ***For Linux:***
    * Jump to definition = ``Super+Click``
    * Jump to definition = ``Control+Super+Alt+Up``
    * Go back = ``Control+Super+Alt+Left``
    * Manual Code Intelligence = ``Control+Shift+space``

  ***For Windows:***
    * Jump to definition = ``Alt+Click``
    * Jump to definition = ``Control+Windows+Alt+Up``
    * Go back = ``Control+Windows+Alt+Left``
    * Manual Code Intelligence = ``Control+Shift+space``

Don't despair! The first time you use it it needs to build some indexes and it can take more than a few seconds.

It just works!


Configuring
-----------
Basic settings can be configured in the User File Settings.

All settings can be overridden in the *.sublime-project file under the value "codeintel_settings". For Example::

    {
        "codeintel_settings":
        {
            "codeintel_database_dir": "~/.codeintel/databases/myProject",
            "codeintel_language_settings":
            {
                "JavaScript": {
                    "codeintel_scan_files_in_project": true,
                    "codeintel_scan_exclude_dir": ["/min/"]
                }
            }
        }
    }

If you put this in your *.sublime-project file, the codeintel-machine will use the given directory as its database,
scan the project folders for JavaScript source files but exclude paths that somehow match with the regular expression "/min/"


To define settings specifically for a language, use the "codeintel_language_settings" setting. Example::

    {
        "codeintel_settings":
        {
            "codeintel_language_settings":
            {
                "PHP": {
                    "php": '/usr/bin/php',
                    "phpConfigFile": 'php.ini',
                    "codeintel_live": true
                },
                "Perl": {
                    "perl": "/usr/bin/perl",
                    "codeintel_tooltips": "popup"
                },
                "Ruby": {
                    "ruby": "/usr/bin/ruby",
                    "codeintel_word_completions": "buffer"
                },
                "Python": {
                    "python": '/usr/bin/python',
                    "codeintel_scan_extra_dir": ["dir/one", "dir/two"]
                },
                "Python3": {
                    "python3": '/usr/bin/python3',
                    "codeintel_selected_catalogs": ["PyWin32"]
                }
            }
        }
    }

This is an extreme example, but should give you an impression of the flexibility of the language settings.

For adding additional library paths (django and extra libs paths for Python or extra paths to look for .js files for JavaScript for example), either add those paths as folders to your project, use the "codeintel_scan_extra_dir" setting.
It is recommended to configure this setting on a "per-language" basis, as a great number of import dirs will slow down the autocompletion process.



Do NOT edit the default CodeComplice settings. Your changes will be lost when CodeComplice is updated. ALWAYS edit the user CodeComplice settings by selecting "Preferences->Package Settings->CodeComplice->Settings - User". Note that individual settings you include in your user settings will **completely** replace the corresponding default setting, so you must provide that setting in its entirety.

Available settings:

* Information for all possible settings is available in the ``CodeComplice.sublime-settings`` file in the package.


Troubleshooting
---------------

To force re-indexation of the code intelligence database you need to follow these steps:

+ Close Sublime Text

+ Open a terminal or navigate through your directories to find the database directory (default:``~/.codeintel``) that contains ``codeintel.log``, ``VERSION`` and the directory ``db``. In Windows, this should be at ``%userprofile%\.codeintel``.

+ Delete the whole directory and all of its content.

+ Start Sublime Text and enjoy a clean re-indexing!


What's New
----------

v1.1.2 (2015-03-09):

+ fix Ruby support and Rails catalog

+ improve working with very large buffers (>10000 lines)

+ PHP: fix goto_defn of extended class, if interface is also implemented

+ JS: improve jQuery catalog with Deferred, Promise and jqXHR objects

v1.1.1 (2015-02-18):

+ zipping stdlibs, reducing plugin size by 2/3.

+ JavaScript: adjust minimal trigger length from 4 to 3 chars.

+ remove extensive JavaScript info logging -> speedup

+ separate trigger_types in JavaScript -> speedup

+ fix doublettes in JavaScript calltips


v1.1.0 (2015-02-15):

+ added support for golang. ported from [komodo-go](https://github.com/Komodo/komodo-go)

+ avoid unnecessary trigger evaluation
    this will be a appreciable speedup on older systems


v1.0.6 (2015-02-11):

+ [this](https://github.com/SublimeCodeIntel/SublimeCodeIntel/issues/477) is now working

+ Python Trigger complete-local-symbols (the full way, not the SublimeCodeIntel way!)

+ usability tweaks


License
-------
The plugin is based in code from the Open Komodo Editor and has a MPL license.

Ported from Open Komodo by German M. Bravo (Kronuz).

Uses CSS from [Intellitip](https://github.com/jbrooksuk/Intellitip) under the
MIT License.
