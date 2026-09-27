"""Read-only identity check: manifest, config and rootfs digests are distinct."""
import hashlib,json

def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def verify(inspect,manifest_raw,config_raw,expected_config,records):
    m=json.loads(manifest_raw);c=json.loads(config_raw)
    assert digest(config_raw)==expected_config,'config identity'
    assert m['config']['digest']==expected_config and m['config']['size']==len(config_raw),'manifest config link'
    assert inspect['Id']==digest(manifest_raw),'runtime manifest identity'
    assert inspect['Os']=='linux' and inspect['Architecture']=='amd64','platform'
    expected=[x['diff_id'] for x in records]
    assert c['rootfs']['diff_ids']==expected==inspect['RootFS']['Layers'],'rootfs'
    assert len(m['layers'])==len(records),'layer count'
    for layer,record in zip(m['layers'],records):
        assert layer['mediaType']=='application/vnd.docker.image.rootfs.diff.tar','legacy uncompressed representation'
        assert layer['digest']==record['diff_id'] and layer['size']==record['uncompressed_bytes'],'layer binding'
    return dict(runtime_manifest_digest=digest(manifest_raw),configuration_digest=expected_config,
        rootfs_diff_ids_match=True,configuration_bytes_match=True,layer_descriptors_match=True)
