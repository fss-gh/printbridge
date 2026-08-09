# GitHub repository community health files
# These are picked up by GitHub automatically

# Enable Discussions tab
# (This is configured in GitHub repo settings, not a file)
# Go to: Settings > General > Features > Discussions ✓

# Enable Issues tab
# Go to: Settings > General > Features > Issues ✓

# Enable Projects tab
# Go to: Settings > General > Features > Projects ✓

# Enable Wiki tab
# Go to: Settings > General > Features > Wiki ✓

# Branch protection rules (configure in GitHub UI):
# Settings > Branches > Add rule for 'main':
#   ✓ Require a pull request before merging
#   ✓ Require status checks to pass before merging
#     - Required: "lint-and-test" (Ubuntu + macOS)
#   ✓ Require branches to be up to date before merging
#   ✓ Do not allow bypassing the above settings
#   ✓ Require linear history
#   ✓ Allow force pushes: No
#   ✓ Allow deletions: No
