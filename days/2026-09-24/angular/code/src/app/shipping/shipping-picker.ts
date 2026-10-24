import { Component, computed, linkedSignal, signal } from '@angular/core';

interface ShippingOption {
  id: string;
  label: string;
  price: number;
}

const OPTIONS_BY_COUNTRY: Record<'PL' | 'DE', ShippingOption[]> = {
  PL: [
    { id: 'inpost', label: 'InPost Paczkomat', price: 9.99 },
    { id: 'courier', label: 'Kurier', price: 14.99 },
  ],
  DE: [
    { id: 'dhl', label: 'DHL', price: 12.5 },
    { id: 'courier-de', label: 'Kurier DE', price: 19.99 },
  ],
};

@Component({
  selector: 'app-shipping-picker',
  templateUrl: './shipping-picker.html',
})
export class ShippingPicker {
  protected readonly country = signal<'PL' | 'DE'>('PL');

  protected readonly options = computed(() => OPTIONS_BY_COUNTRY[this.country()]);

  // linkedSignal() (nowość - Angular 19) - jak computed(), ale wynik można też
  // ręcznie NADPISAĆ przez set()/update(), tak jak zwykły signal(). Gdy sygnał
  // źródłowy (tu: options(), zależny od country()) się zmieni, wybór AUTOMATYCZNIE
  // resetuje się do wartości domyślnej z funkcji linkującej - dokładnie tak, jak
  // w prawdziwym formularzu: zmiana kraju kasuje wcześniej ręcznie wybraną metodę
  // wysyłki i podpowiada nową domyślną. Zwykły computed() by tu nie wystarczył
  // (jest tylko-do-odczytu), a zwykły signal() nie wiedziałby, kiedy się zresetować.
  protected readonly selectedShipping = linkedSignal(() => this.options()[0]);

  protected readonly total = computed(() => this.selectedShipping().price);

  protected setCountry(country: 'PL' | 'DE'): void {
    this.country.set(country);
  }

  protected selectShipping(option: ShippingOption): void {
    this.selectedShipping.set(option);
  }
}
