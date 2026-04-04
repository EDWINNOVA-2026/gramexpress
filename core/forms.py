from django import forms

from .models import (
    CustomerProfile,
    Order,
    PaymentMethod,
    Product,
    RoleType,
    Shop,
    ShopType,
    VehicleType,
)

ACCOUNT_TYPE_CHOICES = [choice for choice in RoleType.choices if choice[0] != RoleType.ADMIN]
LANGUAGE_CHOICES = [
    ('en', 'English'),
    ('hi', 'Hindi'),
    ('kn', 'Kannada'),
]
REGISTRATION_ROLE_FIELDS = {
    RoleType.CUSTOMER: ['preferred_language', 'address_line_1', 'address_line_2', 'district', 'pincode', 'latitude', 'longitude'],
    RoleType.SHOP: ['shop_name', 'shop_type', 'area', 'address_line_1', 'address_line_2', 'district', 'pincode', 'description', 'offer', 'latitude', 'longitude'],
    RoleType.RIDER: ['age', 'vehicle_type', 'latitude', 'longitude'],
}


class BaseStyledForm:
    def _style_fields(self):
        for name, field in self.fields.items():
            css_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{css_class} input'.strip()
            if 'placeholder' not in field.widget.attrs and not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['placeholder'] = field.label
            if isinstance(field.widget, forms.PasswordInput):
                field.widget.attrs['autocomplete'] = 'current-password'
            elif isinstance(field.widget, forms.EmailInput):
                field.widget.attrs['autocomplete'] = 'email'
            elif isinstance(field.widget, forms.NumberInput):
                field.widget.attrs['inputmode'] = 'numeric'
            elif name == 'phone':
                field.widget.attrs['autocomplete'] = 'tel'
                field.widget.attrs['inputmode'] = 'tel'


class LoginForm(forms.Form, BaseStyledForm):
    identity = forms.CharField(max_length=120, label='Phone or email')
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields['identity'].widget.attrs['autofocus'] = 'autofocus'
        self.fields['identity'].widget.attrs['autocomplete'] = 'username'
        self.fields['identity'].widget.attrs['placeholder'] = 'Enter phone number or email'
        self.fields['password'].widget.attrs['placeholder'] = 'Enter your password'


class RoleLoginForm(LoginForm):
    pass


class LoginOtpVerifyForm(forms.Form, BaseStyledForm):
    code = forms.CharField(max_length=6, min_length=6, label='OTP code')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields['code'].widget.attrs['placeholder'] = 'Enter 6 digit OTP'
        self.fields['code'].widget.attrs['inputmode'] = 'numeric'
        self.fields['code'].widget.attrs['autocomplete'] = 'one-time-code'


class EmailOtpRequestForm(forms.Form, BaseStyledForm):
    email = forms.EmailField(label='Email address')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields['email'].widget.attrs['placeholder'] = 'Enter your registered email'


class EmailOtpVerifyForm(forms.Form, BaseStyledForm):
    email = forms.EmailField(label='Email address')
    code = forms.CharField(max_length=6, min_length=6, label='OTP code')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields['email'].widget.attrs['placeholder'] = 'Enter the same email again'
        self.fields['code'].widget.attrs['placeholder'] = 'Enter 6 digit OTP'
        self.fields['code'].widget.attrs['inputmode'] = 'numeric'


class UnifiedRegistrationForm(forms.Form, BaseStyledForm):
    account_type = forms.ChoiceField(choices=ACCOUNT_TYPE_CHOICES, label='Register as')
    full_name = forms.CharField(max_length=120, label='Full name')
    phone = forms.CharField(max_length=20, label='Mobile number')
    email = forms.EmailField(label='Email address')
    password1 = forms.CharField(widget=forms.PasswordInput, label='Password')
    password2 = forms.CharField(widget=forms.PasswordInput, label='Confirm password')
    preferred_language = forms.ChoiceField(choices=LANGUAGE_CHOICES, required=False)
    address_line_1 = forms.CharField(max_length=160, required=False, label='Address line 1')
    address_line_2 = forms.CharField(max_length=160, required=False, label='Address line 2')
    district = forms.CharField(max_length=80, required=False)
    pincode = forms.CharField(max_length=12, required=False)
    latitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False)
    longitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False)
    shop_name = forms.CharField(max_length=140, required=False, label='Shop name')
    shop_type = forms.ChoiceField(choices=ShopType.choices, required=False)
    area = forms.CharField(max_length=120, required=False)
    description = forms.CharField(
        max_length=300,
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )
    offer = forms.CharField(max_length=160, required=False)
    age = forms.IntegerField(min_value=18, max_value=80, required=False)
    vehicle_type = forms.ChoiceField(choices=VehicleType.choices, required=False)

    def __init__(self, *args, **kwargs):
        selected_role = kwargs.pop('selected_role', '')
        super().__init__(*args, **kwargs)

        if selected_role in REGISTRATION_ROLE_FIELDS:
            keep_fields = {
                'account_type',
                'full_name',
                'phone',
                'email',
                'password1',
                'password2',
                *REGISTRATION_ROLE_FIELDS[selected_role],
            }
            for field_name in list(self.fields):
                if field_name not in keep_fields:
                    self.fields.pop(field_name)
            self.fields['account_type'].initial = selected_role
            self.fields['account_type'].widget = forms.HiddenInput()

        self._style_fields()

        if 'full_name' in self.fields:
            self.fields['full_name'].widget.attrs['autocomplete'] = 'name'
        if 'email' in self.fields:
            self.fields['email'].widget.attrs['placeholder'] = 'you@example.com'
        if 'password1' in self.fields:
            self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'
        if 'address_line_1' in self.fields:
            self.fields['address_line_1'].widget.attrs['autocomplete'] = 'address-line1'
        if 'address_line_2' in self.fields:
            self.fields['address_line_2'].widget.attrs['autocomplete'] = 'address-line2'
        if 'district' in self.fields:
            self.fields['district'].widget.attrs['autocomplete'] = 'address-level2'
        if 'pincode' in self.fields:
            self.fields['pincode'].widget.attrs['autocomplete'] = 'postal-code'
        if 'latitude' in self.fields:
            self.fields['latitude'].widget.attrs['readonly'] = True
        if 'longitude' in self.fields:
            self.fields['longitude'].widget.attrs['readonly'] = True

    def clean(self):
        cleaned_data = super().clean()
        account_type = cleaned_data.get('account_type')
        if cleaned_data.get('password1') != cleaned_data.get('password2'):
            self.add_error('password2', 'Passwords did not match.')

        required_fields_by_role = {
            RoleType.CUSTOMER: ['preferred_language', 'address_line_1', 'district', 'pincode', 'latitude', 'longitude'],
            RoleType.SHOP: ['shop_name', 'shop_type', 'area', 'address_line_1', 'district', 'pincode', 'latitude', 'longitude'],
            RoleType.RIDER: ['age', 'vehicle_type', 'latitude', 'longitude'],
        }
        for field_name in required_fields_by_role.get(account_type, []):
            if cleaned_data.get(field_name) in [None, '']:
                self.add_error(field_name, 'This field is required for the selected account type.')

        return cleaned_data


class CustomerOnboardingForm(forms.ModelForm, BaseStyledForm):
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = CustomerProfile
        fields = [
            'full_name',
            'phone',
            'email',
            'preferred_language',
            'address_line_1',
            'address_line_2',
            'district',
            'pincode',
            'latitude',
            'longitude',
        ]
        widgets = {
            'preferred_language': forms.Select(choices=LANGUAGE_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields['full_name'].widget.attrs['autocomplete'] = 'name'
        self.fields['address_line_1'].widget.attrs['autocomplete'] = 'address-line1'
        self.fields['address_line_2'].widget.attrs['autocomplete'] = 'address-line2'
        self.fields['district'].widget.attrs['autocomplete'] = 'address-level2'
        self.fields['pincode'].widget.attrs['autocomplete'] = 'postal-code'
        self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password1') != cleaned_data.get('password2'):
            self.add_error('password2', 'Passwords did not match.')
        return cleaned_data


class CustomerProfileForm(forms.ModelForm, BaseStyledForm):
    class Meta:
        model = CustomerProfile
        fields = [
            'full_name',
            'email',
            'preferred_language',
            'address_line_1',
            'address_line_2',
            'district',
            'pincode',
            'latitude',
            'longitude',
        ]
        widgets = {
            'preferred_language': forms.Select(choices=LANGUAGE_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields['full_name'].widget.attrs['autocomplete'] = 'name'
        self.fields['email'].widget.attrs['autocomplete'] = 'email'


class CustomerLocationForm(forms.Form, BaseStyledForm):
    latitude = forms.DecimalField(max_digits=9, decimal_places=6)
    longitude = forms.DecimalField(max_digits=9, decimal_places=6)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ShopOwnerOnboardingForm(forms.Form, BaseStyledForm):
    full_name = forms.CharField(max_length=120)
    phone = forms.CharField(max_length=20)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)
    shop_name = forms.CharField(max_length=140)
    shop_type = forms.ChoiceField(choices=ShopType.choices)
    area = forms.CharField(max_length=120)
    address_line_1 = forms.CharField(max_length=160)
    address_line_2 = forms.CharField(max_length=160, required=False)
    district = forms.CharField(max_length=80)
    pincode = forms.CharField(max_length=12)
    description = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={'rows': 3}))
    offer = forms.CharField(max_length=160, required=False)
    image_url = forms.URLField(required=False)
    image = forms.FileField(required=False)
    latitude = forms.DecimalField(max_digits=9, decimal_places=6)
    longitude = forms.DecimalField(max_digits=9, decimal_places=6)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields['full_name'].widget.attrs['autocomplete'] = 'name'
        self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['shop_name'].widget.attrs['placeholder'] = 'Store name'

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password1') != cleaned_data.get('password2'):
            self.add_error('password2', 'Passwords did not match.')
        return cleaned_data


class RiderOnboardingForm(forms.Form, BaseStyledForm):
    full_name = forms.CharField(max_length=120)
    phone = forms.CharField(max_length=20)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)
    age = forms.IntegerField(min_value=18, max_value=80)
    vehicle_type = forms.ChoiceField(choices=VehicleType.choices)
    photo_url = forms.URLField(required=False)
    photo = forms.FileField(required=False)
    latitude = forms.DecimalField(max_digits=9, decimal_places=6)
    longitude = forms.DecimalField(max_digits=9, decimal_places=6)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields['full_name'].widget.attrs['autocomplete'] = 'name'
        self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password1') != cleaned_data.get('password2'):
            self.add_error('password2', 'Passwords did not match.')
        return cleaned_data


class ShopUpdateForm(forms.ModelForm, BaseStyledForm):
    class Meta:
        model = Shop
        fields = [
            'name',
            'shop_type',
            'area',
            'address_line_1',
            'address_line_2',
            'district',
            'pincode',
            'description',
            'offer',
            'image_url',
            'image',
            'latitude',
            'longitude',
            'is_open',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ProductForm(forms.ModelForm, BaseStyledForm):
    class Meta:
        model = Product
        fields = [
            'name',
            'subtitle',
            'category',
            'unit',
            'price',
            'stock',
            'tag',
            'image_url',
            'color',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class CustomerOrderMetaForm(forms.Form, BaseStyledForm):
    payment_method = forms.ChoiceField(choices=PaymentMethod.choices)
    customer_notes = forms.CharField(max_length=200, required=False)

    def __init__(self, *args, **kwargs):
        enable_razorpay = kwargs.pop('enable_razorpay', True)
        super().__init__(*args, **kwargs)
        if not enable_razorpay:
            self.fields['payment_method'].choices = [
                choice for choice in PaymentMethod.choices if choice[0] != PaymentMethod.RAZORPAY
            ]
        self._style_fields()


class RatingForm(forms.ModelForm, BaseStyledForm):
    class Meta:
        model = Order
        fields = ['customer_rating', 'customer_review']
        widgets = {
            'customer_rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'customer_review': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class StoreRatingForm(forms.ModelForm, BaseStyledForm):
    class Meta:
        model = Order
        fields = ['store_rating', 'store_review']
        widgets = {
            'store_rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'store_review': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class RiderLocationForm(forms.Form, BaseStyledForm):
    latitude = forms.DecimalField(max_digits=9, decimal_places=6)
    longitude = forms.DecimalField(max_digits=9, decimal_places=6)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
