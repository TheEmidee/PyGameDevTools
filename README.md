# GameDevTools

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) 
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/) 

---

## Overview ✅

**GameDevTools** is a collection of Python tools and utilities used in the game development

---

## Table of Contents 📚

- [Features](#features-)
- [Requirements](#requirements-)
- [Usage Examples](#usage-examples-)
- [Development & Testing](#development--testing-)
- [Contribution Guide](#contribution-guide-)
- [Support & Troubleshooting](#support--troubleshooting-)
- [License & Credits](#license--credits-)

---

## Features ✨

- Modules to copy a folder or files to a remote location or cloud drive (Amazon S3)

---

## Requirements ⚙️

- Python 3.10 or newer

---


## Usage Examples 🔧

- `uepyscripts.tools.archives.rotate_archives` : this module allows to archive the result of packaging your game, in a shared folder. The arguments are:
   - `directory_path` : The folder where to archive the packages. Note that this module will copy the archives in a sub-folder named after the current date with the format `YYYYMMdd`. If a folder already exists with the same date, it will suffix with an incrementing counter `_XX`
   - `keep_count` : How many versions of the packages you want to keep in `directory_path`. This will remove the extraneous sub-folders to only keep `keep_count` items.
   - `folder_output_file_name` : Path to a text file where to write the path to the folder where the archive was copied. This is useful if you plan to use this folder for other tasks, such as sending a message in slack, or uploading the archives to an amazon S3 bucket

- `uepyscripts.tools.archives.upload_archives` : this module allows to upload to an amazon S3 bucket all the files inside a folder. The arguments are:
   - `local_folder` : The folder where to find the files to upload
   - `bucket_name` : The S3 bucket name
   - `region` : The region of the bucket
   - `access_key` and `secret_key` : The keys to access the bucket
   - `destination_folder` : The folder where to upload in the bucket. As with `rotate_archives`, a sub-folder with the date will be used, and if the folder exists, a suffix will be added.
   - `keep_count` : Same as with `rotate_archives`, this is used to control how many archives you want to keep.
   - `output_file` : Path to a text file where the uploaded files URLs will be stored. This can be used in your jenkinsfile to be sent to a slack channel for example.

Here's an example of how we use these 2 modules in our jenkinsfiles:

```groovy
stage( 'Rotate Archives' ) {
    pwsh """
        . "Scripts/PyScripts/.venv/Scripts/ue-tools-archives-rotate.exe" `
          --directory_path = "//nas/Versions/OurGame/Development/WIP" `
          --keep_count = "-1" `
          --folder_output_file_name = "${env.WORKSPACE}/Saved/Temp/latest_archive_Development.txt"
    """

    def folder_name = readFile "${env.WORKSPACE}/Saved/Temp/latest_archive_Development.txt"
    slackSend( channel: '#channel', message: "New Development build available : ${folder_name}" )
}

stage( 'Upload Archives' ) {
    def file = readFile "${env.WORKSPACE}/Saved/Temp/latest_archive_Development.txt"

    pwsh """
        . "Scripts/PyScripts/.venv/Scripts/ue-tools-archives-upload.exe" `
            --local_folder = "${file}" `
            --bucket_name = "artifacts" `
            --region = "eu-west-3" `
            --access_key = "XXXXX" `
            --secret_key = "YYYYY" `
            --destination_folder = "Development/" `
            --keep_count = "-1" `
            --output_file = "${env.WORKSPACE}/Saved/Temp/uploaded_files_Development.txt" `
    """

    def uploaded_files = readFile "${env.WORKSPACE}/Saved/Temp/uploaded_files_Development.txt"
    def lines = uploaded_files.split('\n')

    if ( lines.size() > 0 ) {
        def message = 'Uploaded builds:\n'

        lines.each { String line ->
            def parts = line.split(' : ', 2)
            if (parts.size() == 2) {
                def url = parts[0].trim()
                def filename = parts[1].trim()
                message += "<${url}|${filename}>\n"
            }
        }

        slackSend( channel: '#channel', message: message )
    } else {
        slackSend( channel: '#channel', color: 'danger', message: 'No files were uploaded' )
    }
}
```

## Development & Testing 🧪

- Setup dev environment and install dependencies:

  ```powershell
  .\setup_venv.ps1
  .\.venv\Scripts\Activate.ps1
  ```

- Linting & formatting
  - Use `ruff check .`, `ruff format .` and `mypy .`

---

## Contribution Guide 🤝

We welcome contributions — please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-change`
4. Run lint locally
5. Submit a pull request describing the change

---

## Support & Troubleshooting ❓

- Check `Config/` and `uepyscripts/internal/config.py` for project-specific settings.
- If `buildgraph` fails, ensure `Config/Project` has a valid `BuildgraphPath` and the UAT tool is accessible.
- When reporting issues, include:
  - Python version
  - Unreal Engine version
  - Exact command and full logs

---

## License & Credits 📝

**License:** MIT — see the [LICENSE](LICENSE) file.

**Maintainers:** Michael Delva and contributors (see `AUTHORS` or repository metadata).

**Changelog:** See [CHANGELOG.md](CHANGELOG.md)

---

Made with ❤️ for Game Dev developers — contributions and feedback are welcome! If this helped you, consider starring the repository. ⭐

