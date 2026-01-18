function a() {
    // 引入并使用
    const JSEncrypt = require('jsencrypt');
    var encrypt = new JSEncrypt()
    RSAPublicKey = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvAKBZE0Ez4lIlFFO1MO2i/RZVKgHMoxTyVM/WZoiIZRDWV6TzdKYAikE6yb/7nBg4b9NcU0NxmwSTihHngD9n9EDOhYc2IpRsJLjTqd4sgt65cE5IeIQiymNZrg6ck8xOLldSeMMSC2fz3UneTIoXunj3rPWgCEwmwYLx2nlh+GUh4lIuV4LrbpySe1DYUkrLeW2CMnFg4Kd+OjSrd3niJ/v92ZJFGYYBS1fkdZPpvHEAM2yk7oSTGsuZx4/lSCngjO+yxs7ppxj5ta57XX6iZPV1baRUmWirU/G+s7HtyVx5Jo2r4hUVjhTnKTvEBK14IsK3dqqXJTabkRVKVP5qwIDAQAB"
    encrypt.setPublicKey(RSAPublicKey);
    var password = encrypt.encrypt("Wzy123888!")

    console.log(password)
    return password
}
a()