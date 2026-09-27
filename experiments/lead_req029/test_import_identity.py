import copy,json,unittest
from import_identity import verify,digest
class Tests(unittest.TestCase):
 def test_representation_and_substitutions(self):
  cfg=json.dumps({'rootfs':{'diff_ids':['sha256:abc']}}).encode();pin=digest(cfg)
  m={'config':{'digest':pin,'size':len(cfg)},'layers':[{'mediaType':'application/vnd.docker.image.rootfs.diff.tar','digest':'sha256:abc','size':1024}]}
  raw=json.dumps(m).encode();i={'Id':digest(raw),'Os':'linux','Architecture':'amd64','RootFS':{'Layers':['sha256:abc']}}
  records=[{'diff_id':'sha256:abc','uncompressed_bytes':1024}]
  self.assertNotEqual(i['Id'],pin);self.assertTrue(verify(i,raw,cfg,pin,records)['rootfs_diff_ids_match'])
  for key,value in [('Id',pin),('Architecture','arm64'),('RootFS',{'Layers':[]})]:
   bad=copy.deepcopy(i);bad[key]=value
   with self.assertRaises(AssertionError):verify(bad,raw,cfg,pin,records)
  with self.assertRaises(AssertionError):verify(i,raw,cfg+b' ',pin,records)
  bad=copy.deepcopy(m);bad['layers'][0]['size']=1025;b=json.dumps(bad).encode();j=dict(i,Id=digest(b))
  with self.assertRaises(AssertionError):verify(j,b,cfg,pin,records)
if __name__=='__main__':unittest.main()
