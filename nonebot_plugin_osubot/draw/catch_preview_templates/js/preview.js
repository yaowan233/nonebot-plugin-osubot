var bgblob;
function Preview(dest) {
    this.container = dest;

    this.screen = document.createElement('canvas');
    this.screen.width = Beatmap.WIDTH;
    this.screen.height = Beatmap.HEIGHT;
    this.ctx = this.screen.getContext('2d');
    this.container.appendChild(this.screen);

    var self = this;
    this.background = new Image();
    this.background.setAttribute('crossOrigin', 'anonymous');
    let drawBG = function () {
        var canvas = document.createElement('canvas');
        canvas.id = 'bgcanvas';
        canvas.width = self.screen.width;
        canvas.height = self.screen.height;
        var ctx = canvas.getContext('2d');

        // background-size: cover height
        var sWidth = this.height * (self.screen.width / self.screen.height);
        ctx.drawImage(this, (this.width - sWidth) / 2, 0, sWidth, this.height,
            0, 0, self.screen.width, self.screen.height);
        // background dim
        ctx.fillStyle = 'rgba(0, 0, 0, .5)';
        ctx.fillRect(0, 0, self.screen.width, self.screen.height);

        if (typeof self.beatmap.processBG != 'undefined') {
            self.beatmap.processBG(ctx);
        }
        canvas.toBlob(function (blob) {
            var url = URL.createObjectURL(blob);
            self.background.src = url;
            self.container.style.backgroundImage = 'url(' + url + ')';
        });
    }
    this.background.addEventListener('load', drawBG, { once: true });
    this.background.addEventListener('error', function () {
        self.container.style.backgroundImage = 'none';
    });
}
Preview.prototype.load = function (bgblob, osufile, mod, success, fail) {
    if (typeof this.xhr != 'undefined') {
        this.xhr.abort();
    }

    let mods = {
        HR: false,
        EZ: false
    }
    if (mod) mods[mod] = true;

    var self = this;
    try {
        self.beatmap = Beatmap.parse(osufile, mods);
        if (bgblob) self.background.src = bgblob;
        self.ctx.restore();
        self.ctx.save();
        self.beatmap.update(self.ctx);
        self.at(0);

        if (typeof success == 'function') {
            success.call(self);
        }
    }
    catch (e) {
        if (typeof fail == 'function') {
            fail.call(self, e);
        }
    }
};
Preview.prototype.at = function (time) {
    this.ctx.save();
    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.clearRect(0, 0, Beatmap.WIDTH, Beatmap.HEIGHT);
    this.ctx.restore();
    this.beatmap.draw(time, this.ctx);
};

Preview.prototype.output = function () {
    let SCALE = 0.2;
    let canvas2 = this.beatmap.draw2(SCALE);
    canvas2.toBlob(function (blob) {
        // 创建下载链接
        let link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "预览图.png";

        // 触发下载
        link.click();
    }, "image/png");
};
