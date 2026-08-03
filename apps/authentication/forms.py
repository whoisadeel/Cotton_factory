"""
Authentication Forms
"""
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordChangeForm
from .models import User, LoginAttempt

INPUT = ('w-full px-4 py-3 border-2 border-gray-200 rounded-xl text-sm outline-none '
         'focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 transition-all')
INPUT_STYLE = 'width:100%;padding:10px 14px;border:2px solid #e5e7eb;border-radius:12px;font-size:14px;outline:none;'


class LoginForm(forms.Form):
    """Login form with lockout checking."""
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': INPUT,
            'style': INPUT_STYLE,
            'placeholder': 'Username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': INPUT,
            'style': INPUT_STYLE,
            'placeholder': 'Password',
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-emerald-600 border-gray-300 rounded focus:ring-emerald-500',
            'style': 'width:18px;height:18px;accent-color:#10b981;',
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if username and password:
            if LoginAttempt.is_locked_out(username):
                raise forms.ValidationError(
                    'Account temporarily locked due to too many failed login attempts. '
                    'Please try again after 15 minutes.'
                )

            user = authenticate(username=username, password=password)
            if user is None:
                raise forms.ValidationError('Invalid username or password.')
            if not user.is_active:
                raise forms.ValidationError('This account is inactive.')
            cleaned_data['user'] = user

        return cleaned_data


class ProfileForm(forms.ModelForm):
    """User profile update form."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone',
                  'profile_picture', 'preferred_language']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': INPUT, 'style': INPUT_STYLE}),
            'last_name': forms.TextInput(attrs={'class': INPUT, 'style': INPUT_STYLE}),
            'email': forms.EmailInput(attrs={'class': INPUT, 'style': INPUT_STYLE}),
            'phone': forms.TextInput(attrs={'class': INPUT, 'style': INPUT_STYLE, 'placeholder': '0300-1234567'}),
            'preferred_language': forms.Select(attrs={'class': INPUT, 'style': INPUT_STYLE + 'background:white;'}),
            'profile_picture': forms.FileInput(attrs={
                'class': INPUT,
                'style': INPUT_STYLE,
                'accept': 'image/*',
            }),
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    """Styled password change form."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT
            field.widget.attrs['style'] = INPUT_STYLE


class SecurityQuestionForm(forms.ModelForm):
    """Security question setup for password recovery."""
    class Meta:
        model = User
        fields = ['security_question', 'security_answer']
        widgets = {
            'security_question': forms.Select(
                choices=[
                    ('', 'Select a security question...'),
                    ('mother_name', "What is your mother's maiden name?"),
                    ('first_school', "What was the name of your first school?"),
                    ('birth_city', "In which city were you born?"),
                    ('pet_name', "What was the name of your first pet?"),
                    ('favorite_teacher', "What was the name of your favorite teacher?"),
                ],
                attrs={'class': INPUT, 'style': INPUT_STYLE + 'background:white;'}
            ),
            'security_answer': forms.TextInput(attrs={
                'class': INPUT,
                'style': INPUT_STYLE,
                'placeholder': 'Your answer...',
            }),
        }
