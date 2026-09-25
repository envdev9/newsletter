import { Component } from '@angular/core';
import { Cart } from './cart/cart';
import { Counter } from './counter/counter';
import { Search } from './search/search';
import { ShippingPicker } from './shipping/shipping-picker';

@Component({
  selector: 'app-root',
  imports: [Counter, ShippingPicker, Cart, Search],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly title = 'Angular signals - od podstaw do @ngrx/signals';
}
