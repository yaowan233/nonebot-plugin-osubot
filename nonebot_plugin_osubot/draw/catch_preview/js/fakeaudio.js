function FakeAudio(length) {
    this.src = null;
    this.duration = length;
    this.length = length; // seconds
    this.currentTime = 0; // seconds
    this.volume = 1;
    this.paused = true;
    this.playbackRate = 1;
    this.playTimer = null;
    this.pause();
}

FakeAudio.prototype.draw = function () {
    requestAnimationFrame(() => {
        window.preview.at(this.currentTime * 1000);
    });
}

FakeAudio.prototype.play = function () {
    preview.beatmap.refresh();
    this.draw();
    let ts = 20;
    if (this.paused) {
        $('#play').removeClass('e');
        this.paused = false;
        this.playTimer = setInterval(()=> {
            this.currentTime += ts / 1000 * this.playbackRate;
            if (this.currentTime >= this.length) this.pause();
            if (this.currentTime % 1 < 0.1) {
                $('#progress').val(this.currentTime);
                $('#playtime').text(time2text(this.currentTime));
            }
            this.draw();
        }, ts);
    }
};

FakeAudio.prototype.pause = function () {
    if (this.paused) return;
    $(document.body).trigger('mousemove');
    $('#play').addClass('e');
    this.paused = true;
    clearInterval(this.playTimer);
};