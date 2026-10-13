$(function() {
    'use strict';

    // Form
    var contactForm = function() {
        if ($('#contactForm').length > 0) {
            $("#contactForm").validate({
                rules: {
                    name: "required",
                    email: {
                        required: true,
                        email: true
                    },
                    message: {
                        required: true,
                        minlength: 5
                    }
                },
                messages: {
                    name: "Please enter your name",
                    email: "Please enter a valid email address",
                    message: "Please enter a message"
                },
                /* submit via ajax */
                submitHandler: function(form) {
                    var $submit = $('.submitting'),
                        waitText = 'Submitting...';

                    // Get the CSRF token from the cookies
                    function getCookie(name) {
                        let cookieValue = null;
                        if (document.cookie && document.cookie !== '') {
                            const cookies = document.cookie.split(';');
                            for (let i = 0; i < cookies.length; i++) {
                                const cookie = cookies[i].trim();
                                // Does this cookie string begin with the name we want?
                                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                                    break;
                                }
                            }
                        }
                        return cookieValue;
                    }
                    const csrftoken = getCookie('csrftoken');

                    $.ajax({
                        type: "POST",
                        url: "{% url 'contact' %}", // Make sure this is the correct URL pattern name
                        data: $(form).serialize(),
                        headers: {
                            'X-CSRFToken': csrftoken // Include the CSRF token in the request headers
                        },
                        beforeSend: function() {
                            $submit.css('display', 'block').text(waitText);
                        },
                        success: function(response) {
                            if (response == 'OK') {
                                $('#form-message-warning').hide();
                                setTimeout(function() {
                                    $('#contactForm').fadeOut();
                                }, 1000);
                                setTimeout(function() {
                                    $('#form-message-success').fadeIn();
                                }, 1400);
                            } else {
                                $('#form-message-warning').html(response);
                                $('#form-message-warning').fadeIn();
                                $submit.css('display', 'none');
                            }
                        },
                        error: function() {
                            $('#form-message-warning').html("Something went wrong. Please try again.");
                            $('#form-message-warning').fadeIn();
                            $submit.css('display', 'none');
                        }
                    });
                }
            });
        }
    };
    contactForm();
});
