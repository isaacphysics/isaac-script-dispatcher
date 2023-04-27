# isaac-dispatched-scripts

This repository allows you to dispatch scripts using the [isaac-script-dispatcher](https://github.com/isaacphysics/isaac-script-dispatcher) 
bot.

To request a script run, please open an issue on this repository. We have an issue form set up so that the request is
in a format that the bot can understand. 

The bot will ask you for any required arguments to the script, which you can provide by replying
in comments on the issue. Please reply in the format that the bot requests, otherwise it may not be able to parse the
arguments properly.

Once the script has run, the bot will post a comment on the issue with the output of the script. If any changes have been
made to the content repository, the bot will also create a pull request and post a comment with the link to it (or a link
to the branch it made changes on if you don't want it to create a PR).

This is still a work in progress, so please let the Isaac tech team know if you encounter any errors or have suggestions for 
more scripts to add.

### Script list

| Script identifier | Description  |   Arguments   |
|----------|:-------------|---------|
| list_question_data |  Lists paths, ids and related content for question pages. | Extra links to consider valid 
| link_checker | Validates links across the content repository|
| find_broken_image_links | Finds all figures in the content which have a src that doesn't point to a file that exists. Relies on the fact that figure sources are relative paths, so if figure sources point to the CDN for example then this will flag them up as "broken". |
| compress_svgs | Compresses all SVGs in the content repository. |
| image_renaming | Renames image/figure files in the content repository | A CSV file containing the old filename and new name of images. Schema: `old_name.ext,new_name`
| image_list | Lists all images in the content repository |
| image_duplicates | Dedupe images across the content repository |

