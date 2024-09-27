/** viewbox stretches child to fit parent proportionally.
 *
 * viewbox must have a child that has two attributes, 'width' and 'height'.
 */
document.addEventListener('DOMContentLoaded', function()
{
    window.addEventListener('resize', thunk);
    thunk();

    function thunk()
    {
        var viewboxes = document.getElementsByClassName('x-viewbox');
        for (var i = 0; i < viewboxes.length; i++)
        {
            onresize.call(viewboxes[i]);
        }
    }

    function onresize()
    {
        var parent = this.parentElement,
            child = this.firstChild,
            w, h, cw, ch, sw, sh, s;

        if (!parent)
        {
            w = window.innerWidth;
            h = window.innerHeight;
        }
        else
        {
            w = parent.scrollWidth;
            h = parent.scrollHeight;
        }

        if (child)
        {
            child.style.transformOrigin = '0 0';

            cw = child.width;
            ch = child.height;
        }
        sw = w / cw;
        sh = h / ch;
        // if viewbox has no child that has proper attributes,
        // ignore size of child and re-calculate scale.
        if ((sw || sh) == NaN)
        {
            sw = w;
            sh = h;
        }

        if (sw > sh)
        {
            this.style.width = sh * cw + 'px';
            this.style.height = h + 'px';
            s = sh;
        }
        else
        {
            this.style.width = w + 'px';
            this.style.height = sw * ch + 'px';
            s = sw;
        }
        if (child)
        {
            child.style.transform = 'scale(' + s + ')';
        }
    }
});
