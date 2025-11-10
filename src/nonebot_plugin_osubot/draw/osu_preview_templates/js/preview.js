var bgblob;
function Preview(SCALE = 0.2) {
    this.screen = document.createElement('canvas');
    this.screen.width = Beatmap.WIDTH;
    this.screen.height = Beatmap.HEIGHT;
    this.ctx = this.screen.getContext('2d');
    this.ctx.scale(SCALE, SCALE);
    this.startTime = 0;
    this.endTime = 0;
    this.previewTime = -1;

    var self = this;
}
Preview.prototype.load = function (osufile, success, fail) {
    if (typeof this.xhr != 'undefined') {
        this.xhr.abort();
    }

    var self = this;
    try {
        self.beatmap = Beatmap.parse(osufile);

        self.ctx.restore();
        self.ctx.save();
        self.beatmap.update(self.ctx);
        self.at(0);

        self.previewTime = self.beatmap.PreviewTime > 0 ? self.beatmap.PreviewTime : -1;

        self.startTime = self.beatmap.HitObjects.length > 0 ? self.beatmap.HitObjects[0].time - 1000 : 0;
        if (self.startTime < 0) {
            self.startTime = 0;
        }
        self.endTime = self.beatmap.HitObjects.length > 0 ? self.beatmap.HitObjects[self.beatmap.HitObjects.length - 1].endTime : 0;

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
    if (time > this.endTime) {
        time = this.endTime;
    }
    if (time < this.startTime) {
        time = this.startTime;
    }
    this.ctx.save();
    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.clearRect(0, 0, Beatmap.WIDTH, Beatmap.HEIGHT);
    this.ctx.restore();
    if (typeof this.beatmap.processBG != 'undefined') {
        this.beatmap.processBG(this.ctx);
    }
    this.beatmap.draw(time, this.ctx);
};
