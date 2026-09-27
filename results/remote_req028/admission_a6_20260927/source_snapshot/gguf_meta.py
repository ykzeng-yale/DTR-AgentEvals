"""Read selected metadata without loading tensors or importing model code."""
import json,struct,sys
def read(path):
    with open(path,'rb') as f:
        def unpack(fmt):return struct.unpack('<'+fmt,f.read(struct.calcsize('<'+fmt)))[0]
        def string():
            n=unpack('Q');return f.read(n).decode('utf-8')
        def value(kind,keep=True):
            fmts={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
            if kind in fmts:return unpack(fmts[kind])
            if kind==8:return string()
            if kind==9:
                subtype=unpack('I');n=unpack('Q')
                for _ in range(n):value(subtype,False)
                return {'array_type':subtype,'array_length':n}
            raise ValueError(kind)
        assert f.read(4)==b'GGUF'
        version=unpack('I');tensors=unpack('Q');count=unpack('Q')
        result={'gguf_version':version,'tensor_count':tensors,'metadata_count':count}
        for _ in range(count):
            key=string();kind=unpack('I');result[key]=value(kind)
        return result
if __name__=='__main__':print(json.dumps(read(sys.argv[1]),indent=2))
