import $ from 'jquery';
import ajaxFrom from 'jquery-form';

export default class Forms {
    constructor() {
        this.initAjaxSubmit();
    }
    initAjaxSubmit() {
        for(var submit of document.querySelectorAll('.js-ajax-submit input')){
            if(submit.type == 'submit' && !submit.dataset.stay_enabled) {
                submit.onclick = function() {
                    this.disabled=true;
                    Forms.submitForm(this.form)
                    return false;
                };
            }
        }
    }

    static submitForm(form) {
        $(form).ajaxForm(function() {
                console.log('success');
        });
    }
}
