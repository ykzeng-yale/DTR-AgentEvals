# REQ-029G — one offline import of acquired Django task image

Lead releases only packaging and one Docker image load using the ten verified REQ-029F layers for django__django-16560. No network download, image build, container creation/start, model, generated action or evaluator is authorized. Task selection remains the first fixed queue entry, not outcome selection. Existing peer images/tags and VM settings remain unchanged.

Exact image configuration SHA256:86afcd19b6c56e5e271a1dfc62177cf03157fe9c9643be560db11480b317cb27. Revalidate each compressed SHA and uncompressed diff_id while producing a legacy Docker archive with the original config bytes and one new tag dtr-owned/req029-django-16560:20260927. Expected uncompressed streams3,130,309,632bytes; archive cap4GiB. Files remain in ignored work/local_req029/django_image_import_20260927. No member is extracted onto the host.

After publishing the pinned source, run once: `.venv/bin/python experiments/lead_req029/image_import.py`. Exclusive output directory prevents replay. Reject preexisting image/tag, require zero containers, normal host pressure/free>=40%,host12GiBreserve,VM>=22GiBavailable(12reserve+10import allowance). Observed before release:host~58GiBavailable and zero containers; prior VMdf~81GiBavailable; rechecked inside script. One serial packer,180CPU-second hard rlimit,nice10,600second client alarm; one300second load-client limit with periodic host checks. No hard Docker-daemon RSS/CPU/disk quota is claimed. On client timeout stop only its exact process group, preserve evidence, classify daemon completion as indeterminate and do not retry or delete peer state. No VM resize/restart/cache cleanup.

Use the existing Docker executable and colima-dtr context; `image load --platform linux/amd64 --input` follows the local CLI and official https://docs.docker.com/reference/cli/docker/image/load/ archive interface. Final image config ID/platform/rootfs must match pins and old tag inventory must remain. A failure is a qualification failure, not permission to substitute a task/image. This import does not establish runtime or test validity; task source/import/storage and no-change/reference controls remain before model cells.

One inert archive-construction test passed: exact config/manifest/layer bytes plus corrupted input rejection, no Docker call. Source pins:
- `experiments/lead_req029/image_import.py`: `6ba0014e3bf65febed487848576dda3ceb6977dc84cccbf6f3bc43d18b7ae85d`
- `experiments/lead_req029/test_image_import.py`: `31148352000be7f0b8ed4969250364c1aa15ca69f2813e844ee2da66c47920ac`

Readiness55%,change0points,range45–65%; competent fixed-target comparison/valid inference, synthesis, independent reproducibility and author-approved package remain.
