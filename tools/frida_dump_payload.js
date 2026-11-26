/* kill shot / libTool.so payload dumper
 * usage: frida -U -f com.Gameplier.TheGhost -l frida_dump_payload.js --no-pause
 */
var BASE_OFF = {
  dlsym_call: 0x5e734c,   // bl 0x5ea950 (dlsym)
  jni_call:   0x5e736c,   // blr x8  (payload JNI_OnLoad)
  decrypt_ret:0x5e7218    // bl 0x5e8a60 返回点
};

Java.perform(function () {
  var m = Process.findModuleByName('libTool.so');
  if (!m) { console.log('[!] libTool.so not loaded'); return; }
  var base = m.base;
  console.log('[+] libTool base = ' + base + ' size=' + m.size);

  Interceptor.attach(base.add(BASE_OFF.dlsym_call), {
    onEnter: function (a) {
      try { console.log('[dlsym] handle=' + a[0] + ' name=' + a[1].readCString()); } catch (e) {}
    },
    onLeave: function (r) { console.log('[dlsym] ret=' + r); }
  });

  Interceptor.attach(base.add(BASE_OFF.decrypt_ret), {
    onEnter: function () { console.log('[decrypt] returned w0=' + this.context.x0); }
  });

  Interceptor.attach(base.add(BASE_OFF.jni_call), {
    onEnter: function () {
      console.log('[+] about to call payload JNI_OnLoad, dumping exec ranges');
      var out = '/data/local/tmp/';
      Process.enumerateRanges('r-x').forEach(function (r) {
        var path = (r.file && r.file.path) || 'anon';
        if (path.indexOf('libTool.so') >= 0) return;
        if (r.size > 0x4000000) return;
        try {
          var data = Memory.readByteArray(r.base, r.size);
          var name = out + 'dump_' + r.base.toString(16).replace('0x','') + '.bin';
          var f = new File(name, 'wb');
          f.write(data); f.flush(); f.close();
          console.log('  saved ' + name + '  size=' + r.size + '  ' + path);
        } catch (e) {}
      });
    }
  });
});
